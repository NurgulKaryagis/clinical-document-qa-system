from unittest.mock import MagicMock

from langchain_core.documents import Document

from app.config import settings
from app.retrieval.hybrid_retriever import (
    RetrievedChunk,
    hybrid_search,
)


def make_mock_store(results):
    store = MagicMock()
    store.similarity_search_with_score.return_value = results
    return store


# --- Scenario 1: alpha must be passed explicitly on every call ---

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
