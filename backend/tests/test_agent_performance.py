import pytest

from app.domains.agents.performance import EvaluationObservation, evaluate_performance


def test_unverified_predictions_never_change_performance_metrics() -> None:
    verified = EvaluationObservation(
        verified=True,
        direction="bullish",
        direction_correct=True,
        confidence=0.8,
        rule_adherent=True,
        condition_key="trend",
    )
    unverified = EvaluationObservation(
        verified=False,
        direction="bearish",
        direction_correct=False,
        confidence=1.0,
        rule_adherent=False,
        condition_key="trend",
    )

    result = evaluate_performance([verified, unverified])

    assert result.verified_sample_size == 1
    assert result.accuracy == 1
    assert result.confidence_calibration_error == pytest.approx(0.2)
    assert result.rule_adherence == 1
    assert result.consistency is None
    assert result.intelligence_score is None


def test_internal_score_is_withheld_until_minimum_verified_sample() -> None:
    sample = EvaluationObservation(
        verified=True,
        direction="bullish",
        direction_correct=True,
        confidence=1,
        rule_adherent=True,
        condition_key="same-condition",
    )

    result = evaluate_performance([sample] * 19)

    assert result.verified_sample_size == 19
    assert result.intelligence_score is None


def test_internal_score_uses_documented_components_after_minimum_sample() -> None:
    sample = EvaluationObservation(
        verified=True,
        direction="bullish",
        direction_correct=True,
        confidence=1,
        rule_adherent=True,
        condition_key="same-condition",
    )

    result = evaluate_performance([sample] * 20)

    assert result.accuracy == 1
    assert result.confidence_calibration_error == 0
    assert result.rule_adherence == 1
    assert result.consistency == 1
    assert result.intelligence_score == 100
