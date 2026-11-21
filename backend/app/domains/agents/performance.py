from collections import Counter, defaultdict
from dataclasses import dataclass

from app.domains.agents.schemas import PerformanceMetrics

METHODOLOGY_VERSION = "agent-evaluation-v1"
MINIMUM_SCORE_SAMPLE = 20


@dataclass(frozen=True)
class EvaluationObservation:
    verified: bool
    direction: str
    direction_correct: bool | None
    confidence: float | None
    rule_adherent: bool | None
    condition_key: str | None


def evaluate_performance(
    observations: list[EvaluationObservation],
) -> PerformanceMetrics:
    """Compute reproducible internal metrics from verified outcomes.

    Accuracy = correct directional decisions / eligible verified decisions.
    Calibration error = mean absolute error between reported confidence and
    directional correctness (0 means calibrated, 1 means maximally wrong).
    Rule adherence = adherent verified decisions / decisions with a recorded
    adherence result. Consistency = mean within-condition modal-direction
    share, only for conditions with at least two verified observations.
    The composite is 100 * (0.35*accuracy + 0.25*(1-calibration_error) +
    0.25*rule_adherence + 0.15*consistency), and is withheld unless at least
    20 verified directional outcomes and every component are available. It is
    an internal workflow diagnostic, not an objective intelligence measure.
    """
    verified = [
        item
        for item in observations
        if item.verified and item.direction_correct is not None
    ]
    accuracy = (
        sum(item.direction_correct is True for item in verified) / len(verified)
        if verified
        else None
    )
    calibrated = [item for item in verified if item.confidence is not None]
    calibration_error = (
        sum(
            abs(item.confidence - float(item.direction_correct))
            for item in calibrated
            if item.confidence is not None
        )
        / len(calibrated)
        if calibrated
        else None
    )
    rule_results = [item.rule_adherent for item in verified if item.rule_adherent is not None]
    rule_adherence = (
        sum(result is True for result in rule_results) / len(rule_results)
        if rule_results
        else None
    )
    by_condition: dict[str, list[str]] = defaultdict(list)
    for item in verified:
        if item.condition_key:
            by_condition[item.condition_key].append(item.direction)
    repeat_groups = [directions for directions in by_condition.values() if len(directions) >= 2]
    consistency = (
        sum(max(Counter(directions).values()) / len(directions) for directions in repeat_groups)
        / len(repeat_groups)
        if repeat_groups
        else None
    )
    components = (accuracy, calibration_error, rule_adherence, consistency)
    score = None
    if len(verified) >= MINIMUM_SCORE_SAMPLE and all(value is not None for value in components):
        assert accuracy is not None
        assert calibration_error is not None
        assert rule_adherence is not None
        assert consistency is not None
        score = 100 * (
            0.35 * accuracy
            + 0.25 * (1 - calibration_error)
            + 0.25 * rule_adherence
            + 0.15 * consistency
        )
    return PerformanceMetrics(
        verified_sample_size=len(verified),
        accuracy=accuracy,
        confidence_calibration_error=calibration_error,
        rule_adherence=rule_adherence,
        consistency=consistency,
        intelligence_score=score,
        methodology_version=METHODOLOGY_VERSION,
    )
