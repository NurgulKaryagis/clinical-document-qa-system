from dataclasses import dataclass

import numpy as np
import weaviate
from langchain_cohere.rerank import CohereRerank
from langchain_community.vectorstores.utils import maximal_marginal_relevance
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_weaviate import WeaviateVectorStore

from app.config import settings


@dataclass
class RetrievedChunk:
    content: str
    section: str
    score: float
    metadata: dict


def build_retriever(
    client: weaviate.WeaviateClient,
    index_name: str
    ) -> WeaviateVectorStore:
    embeddings = OpenAIEmbeddings()
    return WeaviateVectorStore(
        client=client,
        index_name=index_name,
        text_key="content",
        embedding=embeddings,
    )


def hybrid_search(
    store: WeaviateVectorStore,
    query: str,
    k: int = settings.top_k,
) -> list[RetrievedChunk]:
    results: list[tuple[Document, float]] = store.similarity_search_with_score(
        query=query,
        k=k,
        alpha=settings.hybrid_alpha,
    )
    return [
        RetrievedChunk(
            content=doc.page_content,
            section=doc.metadata.get("section", "Unknown Section"),
            score=score,
            metadata=doc.metadata,
        )
        for doc, score in results
    ]


def mmr_search(
    store:WeaviateVectorStore, 
    query: str,
    k: int = settings.mmr_fetch_k,
    ) -> list[RetrievedChunk]:
    query_embedding = np.array(store.embeddings.embed_query(query))
    results : list[tuple[Document, float]] = store.similarity_search_with_score(
        query=query,
        k=k,
        alpha=settings.hybrid_alpha,
        include_vector=True
    )
    candidate_embeddings = [ doc.metadata["vector"]  for doc, _ in results]
    selected_indices = maximal_marginal_relevance(
        query_embedding=query_embedding,
        embedding_list= candidate_embeddings,
        k= settings.top_k,
        lambda_mult= settings.mmr_lambda_mult,
    )
    selected_results = [results[i] for i in selected_indices]
    return [
        RetrievedChunk(
            content=doc.page_content,
            section=doc.metadata.get("section", "Unknown Section"),
            score=score,
            metadata=doc.metadata,
        )
        for doc, score in selected_results
    ]
    
def build_reranker(
    cohere_api_key: str = settings.cohere_api_key,
    model: str = settings.rerank_model,
    top_n: int = settings.rerank_top_n
    ) -> CohereRerank:
    return CohereRerank(
        cohere_api_key=cohere_api_key,
        model=model,
        top_n= top_n
    )
    

def rerank_results(
    reranker: CohereRerank,
    query: str,
    chunks: list[RetrievedChunk]
) -> list[RetrievedChunk]:
    documents = [ Document(page_content=doc.content, metadata=doc.metadata) for doc in chunks]
    results = reranker.compress_documents(
        documents=documents,
        query=query
    )
    return [
        RetrievedChunk(
            content=doc.page_content,
            section=doc.metadata.get("section", "Unknown Section"),
            score=doc.metadata.get("relevance_score"),
            metadata=doc.metadata
        )
    for doc in results
            ]