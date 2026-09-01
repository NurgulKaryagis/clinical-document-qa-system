from dataclasses import dataclass
from typing import List

import weaviate
from langchain_weaviate import WeaviateVectorStore
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings


HYBRID_ALPHA = 0.40
TOP_K = 10


@dataclass
class RetrievedChunk:
    content: str
    section: str
    score: float
    metadata: dict


def build_retriever(client: weaviate.WeaviateClient, index_name: str) -> WeaviateVectorStore:
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
    k: int = TOP_K,
) -> List[RetrievedChunk]:
    results: List[tuple[Document, float]] = store.similarity_search_with_score(
        query=query,
        k=k,
        alpha=HYBRID_ALPHA,
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
