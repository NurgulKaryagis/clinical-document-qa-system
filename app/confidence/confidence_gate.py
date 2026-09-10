from dataclasses import dataclass

from app.config import settings
from app.retrieval.hybrid_retriever import RetrievedChunk


@dataclass
class ConfidenceCheckResult:
    is_confident: bool
    fallback_message: str | None = None
    

def check_confidence(
    chunks: list[RetrievedChunk],
    confidence_threshold: float = settings.confidence_threshold,
    fallback_message: str = settings.fallback_message
) -> ConfidenceCheckResult:
    confidence_score = chunks[0].score if chunks else 0.0
    return ConfidenceCheckResult(
        is_confident= confidence_score >= confidence_threshold,
        fallback_message= None if confidence_score >= confidence_threshold else fallback_message,
    )