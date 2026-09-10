import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "fake-test-key")

from eval.metrics import (
    FAITHFULNESS_THRESHOLD,
    RagasResult,
    build_llm,
    context_precision_wo_reference_mean,
    context_precision_wo_reference_score,
    context_recall_mean,
    context_recall_score,
    faithfulness_mean,
    faithfulness_score,
)


def make_fake_metric(score):
    fake_metric = MagicMock()
    fake_metric.ascore = AsyncMock(return_value=MagicMock(value=score))
    return fake_metric


# --- build_llm ---

def test_build_llm_uses_explicit_api_key():
    with patch("eval.metrics.OpenAI") as mock_openai:
        build_llm(api_key="explicit-key")

    mock_openai.assert_called_once_with(api_key="explicit-key")


def test_build_llm_falls_back_to_env_var():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}), patch("eval.metrics.OpenAI") as mock_openai:
        build_llm(api_key=None)

    mock_openai.assert_called_once_with(api_key="env-key")


# --- faithfulness_score / faithfulness_mean ---

def test_faithfulness_score_returns_metric_value():
    with patch("eval.metrics.Faithfulness", return_value=make_fake_metric(0.92)):
        result = asyncio.run(
            faithfulness_score(user_input="q", response="a", retrieved_context=["ctx"])
        )

    assert result == 0.92


def test_faithfulness_mean_passes_above_threshold():
    result = faithfulness_mean([0.9, 0.95, 0.8])

    assert result == RagasResult(passed=True, score=pytest.approx(0.8833333333333333))


def test_faithfulness_mean_fails_below_threshold():
    result = faithfulness_mean([0.5, 0.6])

    assert result.passed is False
    assert result.score == pytest.approx(0.55)


def test_faithfulness_mean_exact_threshold_passes():
    result = faithfulness_mean([FAITHFULNESS_THRESHOLD])

    assert result.passed is True


def test_faithfulness_mean_result_is_json_serializable():
    import json
    from dataclasses import asdict

    result = faithfulness_mean([0.9, 0.8])

    json.dumps(asdict(result))  # must not raise


# --- context_precision_wo_reference_score / mean ---

def test_context_precision_score_returns_metric_value():
    with patch("eval.metrics.ContextPrecisionWithoutReference", return_value=make_fake_metric(0.7)):
        result = asyncio.run(
            context_precision_wo_reference_score(user_input="q", response="a", retrieved_context=["ctx"])
        )

    assert result == 0.7


def test_context_precision_mean_is_plain_float_not_ragas_result():
    result = context_precision_wo_reference_mean([0.8, 0.6])

    assert result == pytest.approx(0.7)
    assert isinstance(result, float)


# --- context_recall_score / mean ---

def test_context_recall_score_passes_reference_not_response():
    fake_metric = make_fake_metric(0.65)
    with patch("eval.metrics.ContextRecall", return_value=fake_metric):
        result = asyncio.run(
            context_recall_score(user_input="q", retrieved_context=["ctx"], reference="expected info")
        )

    assert result == 0.65
    fake_metric.ascore.assert_called_once_with(
        user_input="q", retrieved_contexts=["ctx"], reference="expected info"
    )


def test_context_recall_mean_is_plain_float():
    result = context_recall_mean([0.4, 0.6])

    assert result == pytest.approx(0.5)
    assert isinstance(result, float)
