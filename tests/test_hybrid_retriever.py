from unittest.mock import MagicMock
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_community.vectorstores.utils import maximal_marginal_relevance

from app.config import settings
from app.retrieval.hybrid_retriever import (
    RetrievedChunk,
    build_reranker,
    hybrid_search,
    mmr_search,
    rerank_results,
)


def make_mock_store(results):
    store = MagicMock()
    store.similarity_search_with_score.return_value = results
    return store


# --- Scenario 1: alpha must be passed explicitly on every hybrid search call ---

def test_hybrid_search_passes_configured_alpha():
    store = make_mock_store([])

    hybrid_search(store, "metformin dosage")

    store.similarity_search_with_score.assert_called_once_with(
        query="metformin dosage",
        k=settings.top_k,
        alpha=settings.hybrid_alpha,
    )


def test_hybrid_search_passes_custom_k():
    store = make_mock_store([])

    hybrid_search(store, "metformin dosage", k=3)

    store.similarity_search_with_score.assert_called_once_with(
        query="metformin dosage",
        k=3,
        alpha=settings.hybrid_alpha,
    )


# --- Scenario 2: Document + score correctly mapped to RetrievedChunk ---

def test_maps_document_and_score_to_retrieved_chunk():
    doc = Document(page_content="500mg twice daily", metadata={"section": "Dosage"})
    store = make_mock_store([(doc, 0.87)])

    chunks = hybrid_search(store, "metformin dosage")

    assert len(chunks) == 1
    assert isinstance(chunks[0], RetrievedChunk)
    assert chunks[0].content == "500mg twice daily"
    assert chunks[0].section == "Dosage"
    assert chunks[0].score == 0.87
    assert chunks[0].metadata == {"section": "Dosage"}


def test_missing_section_metadata_falls_back_to_unknown():
    doc = Document(page_content="Some text", metadata={})
    store = make_mock_store([(doc, 0.5)])

    chunks = hybrid_search(store, "query")

    assert chunks[0].section == "Unknown Section"


def test_multiple_results_preserve_order():
    doc_a = Document(page_content="A", metadata={"section": "Dosage"})
    doc_b = Document(page_content="B", metadata={"section": "Side Effects"})
    store = make_mock_store([(doc_a, 0.9), (doc_b, 0.6)])

    chunks = hybrid_search(store, "query")

    assert [c.content for c in chunks] == ["A", "B"]
    assert [c.score for c in chunks] == [0.9, 0.6]


# --- Scenario 3: alpha must be passed explicitly on every mmr search call  ---

def test_mmr_search_passes_configured_alpha():
    store = make_mock_store([])

    mmr_search(store, "metformin dosage")

    store.similarity_search_with_score.assert_called_once_with(
        query="metformin dosage",
        k=settings.mmr_fetch_k,
        alpha=settings.hybrid_alpha,
        include_vector=True
    )
    
def test_mmr_search_passes_custom_k():
    store = make_mock_store([])

    mmr_search(store, "metformin dosage", k=3)

    store.similarity_search_with_score.assert_called_once_with(
        query="metformin dosage",
        k=3,
        alpha=settings.hybrid_alpha,
        include_vector=True
    )
    
# --- Scenario 4: lambda must be passed explicitly on every mmr search call  ---

def test_mmr_search_passes_configured_lambda():
    store = make_mock_store([
        (Document(page_content="A", metadata={"vector": [0.1, 0.2]}), 0.9),
    ])

    with patch("app.retrieval.hybrid_retriever.maximal_marginal_relevance", return_value=[0]) as mock_mmr:
        mmr_search(store, "metformin dosage")

    call_kwargs = mock_mmr.call_args.kwargs
    assert call_kwargs["lambda_mult"] == settings.mmr_lambda_mult
    assert call_kwargs["k"] == settings.top_k


# --- Scenario 5: selected_indices must map back to the correct candidate, not just the first one ---

def test_mmr_search_maps_selected_index_to_correct_chunk():
    doc_a = Document(page_content="A", metadata={"section": "Dosage", "vector": [0.1, 0.2]})
    doc_b = Document(page_content="B", metadata={"section": "Contraindications", "vector": [0.9, 0.1]})
    doc_c = Document(page_content="C", metadata={"section": "Side Effects", "vector": [0.5, 0.5]})
    store = make_mock_store([(doc_a, 0.9), (doc_b, 0.8), (doc_c, 0.5)])

    # Pretend MMR picked index 1 (doc_b), not the highest-scored index 0 (doc_a)
    with patch("app.retrieval.hybrid_retriever.maximal_marginal_relevance", return_value=[1]):
        chunks = mmr_search(store, "metformin dosage")

    assert len(chunks) == 1
    assert chunks[0].content == "B"
    assert chunks[0].section == "Contraindications"


def test_mmr_search_maps_multiple_selected_indices_in_returned_order():
    doc_a = Document(page_content="A", metadata={"section": "Dosage", "vector": [0.1, 0.2]})
    doc_b = Document(page_content="B", metadata={"section": "Contraindications", "vector": [0.9, 0.1]})
    doc_c = Document(page_content="C", metadata={"section": "Side Effects", "vector": [0.5, 0.5]})
    store = make_mock_store([(doc_a, 0.9), (doc_b, 0.8), (doc_c, 0.5)])

    # maximal_marginal_relevance can return indices in any order — not just ascending
    with patch("app.retrieval.hybrid_retriever.maximal_marginal_relevance", return_value=[2, 0]):
        chunks = mmr_search(store, "metformin dosage")

    assert [c.content for c in chunks] == ["C", "A"]


# --- Scenario 6: real MMR must actually favor diversity over near-duplicates ---

def test_mmr_search_prefers_diverse_section_over_near_duplicate():
    # doc_b is a near-duplicate of doc_a (very similar vector, same section) and has
    # a slightly higher relevance score. doc_c is a different section, less similar
    # to the query, but meaningfully different from doc_a/doc_b. A relevance-only
    # ranking would keep both doc_a and doc_b; MMR (lambda_mult=0.3, diversity-leaning
    # per ADR-005) should prefer doc_c over doc_b once doc_a is already selected.
    doc_a = Document(page_content="Dosage A", metadata={"section": "Dosage", "vector": [1.0, 0.0]})
    doc_b = Document(page_content="Dosage B (near-duplicate)", metadata={"section": "Dosage", "vector": [0.98, 0.05]})
    doc_c = Document(page_content="Contraindications", metadata={"section": "Contraindications", "vector": [0.2, 0.95]})
    store = make_mock_store([(doc_a, 0.95), (doc_b, 0.93), (doc_c, 0.70)])
    store.embeddings.embed_query.return_value = [1.0, 0.0]

    chunks = mmr_search(store, "metformin dosage", k=3)

    sections_in_order = [c.section for c in chunks]
    assert sections_in_order[0] == "Dosage"
    # The near-duplicate must rank after the diverse chunk, not right after doc_a.
    assert sections_in_order[1] == "Contraindications"


# --- Scenario 7: embedding the query must happen exactly once (regression) ---

def test_mmr_search_embeds_query_exactly_once():
    doc = Document(page_content="A", metadata={"section": "Dosage", "vector": [0.1, 0.2]})
    store = make_mock_store([(doc, 0.9)])
    store.embeddings.embed_query.return_value = [0.1, 0.2]

    mmr_search(store, "metformin dosage")

    store.embeddings.embed_query.assert_called_once_with("metformin dosage")


# --- Scenario 8: build_reranker uses configured settings ---

def test_build_reranker_uses_configured_settings():
    reranker = build_reranker()

    assert reranker.top_n == settings.rerank_top_n
    assert reranker.model == settings.rerank_model


# --- Scenario 9: rerank_results converts chunks to Documents and passes the query ---

def test_rerank_results_converts_chunks_to_documents():
    chunks = [
        RetrievedChunk(content="Dosage info", section="Dosage", score=0.9, metadata={"section": "Dosage"}),
    ]
    fake_reranker = MagicMock()
    fake_reranker.compress_documents.return_value = [
        Document(page_content="Dosage info", metadata={"section": "Dosage", "relevance_score": 0.95}),
    ]

    rerank_results(fake_reranker, "metformin dosage", chunks)

    call_kwargs = fake_reranker.compress_documents.call_args.kwargs
    assert call_kwargs["query"] == "metformin dosage"
    passed_docs = call_kwargs["documents"]
    assert len(passed_docs) == 1
    assert isinstance(passed_docs[0], Document)
    assert passed_docs[0].page_content == "Dosage info"
    assert passed_docs[0].metadata == {"section": "Dosage"}


# --- Scenario 10: the final score must come from Rerank, not the original chunk ---

def test_rerank_results_uses_relevance_score_not_original_score():
    chunks = [
        RetrievedChunk(content="Dosage info", section="Dosage", score=0.5, metadata={"section": "Dosage"}),
    ]
    fake_reranker = MagicMock()
    fake_reranker.compress_documents.return_value = [
        Document(page_content="Dosage info", metadata={"section": "Dosage", "relevance_score": 0.97}),
    ]

    results = rerank_results(fake_reranker, "metformin dosage", chunks)

    assert results[0].score == 0.97
    assert results[0].score != 0.5


# --- Scenario 11: output order must follow the reranker's order, not the input order ---

def test_rerank_results_preserves_reranker_order():
    chunks = [
        RetrievedChunk(content="Dosage info", section="Dosage", score=0.9, metadata={"section": "Dosage"}),
        RetrievedChunk(content="Contraindications info", section="Contraindications", score=0.8, metadata={"section": "Contraindications"}),
    ]
    fake_reranker = MagicMock()
    # Reranker puts the originally-lower-scored chunk first.
    fake_reranker.compress_documents.return_value = [
        Document(page_content="Contraindications info", metadata={"section": "Contraindications", "relevance_score": 0.97}),
        Document(page_content="Dosage info", metadata={"section": "Dosage", "relevance_score": 0.85}),
    ]

    results = rerank_results(fake_reranker, "metformin dosage", chunks)

    assert [r.content for r in results] == ["Contraindications info", "Dosage info"]


def test_rerank_results_missing_section_falls_back_to_unknown():
    chunks = [
        RetrievedChunk(content="Some text", section="Unknown Section", score=0.5, metadata={}),
    ]
    fake_reranker = MagicMock()
    fake_reranker.compress_documents.return_value = [
        Document(page_content="Some text", metadata={"relevance_score": 0.9}),
    ]

    results = rerank_results(fake_reranker, "query", chunks)

    assert results[0].section == "Unknown Section"
