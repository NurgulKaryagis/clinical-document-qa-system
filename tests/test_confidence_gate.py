from app.confidence.confidence_gate import ConfidenceCheckResult, check_confidence
from app.config import settings
from app.retrieval.hybrid_retriever import RetrievedChunk


def make_chunk(score):
    return RetrievedChunk(content="text", section="Dosage", score=score, metadata={})


# --- Scenario 1: above and below the configured threshold ---

def test_score_above_threshold_is_confident():
    result = check_confidence([make_chunk(0.9)])

    assert result == ConfidenceCheckResult(is_confident=True, fallback_message=None)


def test_score_below_threshold_is_not_confident():
    result = check_confidence([make_chunk(0.5)])

    assert result.is_confident is False
    assert result.fallback_message == settings.fallback_message


# --- Scenario 2: boundary — exactly at the threshold counts as confident ---
# ADR-007: fallback triggers when the score is *below* the threshold, so a
# score equal to the threshold must not trigger it.

def test_score_exactly_at_threshold_is_confident():
    result = check_confidence([make_chunk(settings.confidence_threshold)])

    assert result.is_confident is True
    assert result.fallback_message is None


# --- Scenario 3: empty results must not crash and must fall back ---

def test_no_chunks_is_not_confident():
    result = check_confidence([])

    assert result.is_confident is False
    assert result.fallback_message == settings.fallback_message


# --- Scenario 4: only the top-ranked chunk's score is used ---

def test_only_top_chunk_score_is_considered():
    # Top chunk is weak; a later, stronger chunk must not rescue confidence.
    chunks = [make_chunk(0.2), make_chunk(0.95)]

    result = check_confidence(chunks)

    assert result.is_confident is False


# --- Scenario 5: custom threshold overrides the configured default ---

def test_custom_threshold_is_respected():
    result = check_confidence([make_chunk(0.5)], confidence_threshold=0.3)

    assert result.is_confident is True
    assert result.fallback_message is None


# --- Scenario 6: custom fallback message overrides the configured default ---

def test_custom_fallback_message_is_used():
    result = check_confidence([make_chunk(0.1)], fallback_message="custom message")

    assert result.fallback_message == "custom message"
