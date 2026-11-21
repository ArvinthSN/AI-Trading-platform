import math
from datetime import UTC, datetime

from app.domains.agents.schemas import (
    AnalystOutput,
    DebateDecision,
    Direction,
    RiskContext,
    RiskManagerOutput,
)

POLICY_VERSION = "evidence-quorum-v1"
MAX_RISK_CONTEXT_AGE_SECONDS = 60
ANALYSTS = {"fundamental", "sentiment", "technical"}


def deterministic_risk_check(
    context: RiskContext,
    proposed_side: str,
    *,
    checked_at: datetime | None = None,
) -> RiskManagerOutput:
    reasons: list[str] = []
    checked_time = checked_at or datetime.now(UTC)
    if not context.account_connected:
        reasons.append("Authorized account risk context is unavailable.")
    required_values = (
        context.account_exposure,
        context.max_account_exposure,
        context.proposed_notional,
        context.max_position_size,
        context.daily_pnl,
        context.daily_loss_limit,
        context.current_drawdown,
        context.max_drawdown_limit,
        context.observed_at,
    )
    if any(value is None for value in required_values):
        reasons.append("One or more required risk limits or account values are missing.")
    elif context.account_connected:
        assert context.account_exposure is not None
        assert context.max_account_exposure is not None
        assert context.proposed_notional is not None
        assert context.max_position_size is not None
        assert context.daily_pnl is not None
        assert context.daily_loss_limit is not None
        assert context.current_drawdown is not None
        assert context.max_drawdown_limit is not None
        assert context.observed_at is not None
        numeric_values = (
            context.account_exposure,
            context.max_account_exposure,
            context.proposed_notional,
            context.max_position_size,
            context.daily_pnl,
            context.daily_loss_limit,
            context.current_drawdown,
            context.max_drawdown_limit,
        )
        if not all(math.isfinite(value) for value in numeric_values):
            reasons.append("Risk context contains a non-finite numeric value.")
        if context.account_exposure < 0 or context.max_account_exposure < 0:
            reasons.append("Exposure values cannot be negative.")
        if context.daily_loss_limit <= 0 or context.max_position_size <= 0:
            reasons.append("Configured loss and position limits must be positive.")
        if context.current_drawdown < 0 or context.max_drawdown_limit <= 0:
            reasons.append("Drawdown values or configured limit are invalid.")
        age_seconds = (checked_time - context.observed_at).total_seconds()
        if age_seconds < -5 or age_seconds > MAX_RISK_CONTEXT_AGE_SECONDS:
            reasons.append("Risk context is stale or has a future timestamp.")
        if context.proposed_notional <= 0:
            reasons.append("Proposed notional must be positive.")
        if context.proposed_notional > context.max_position_size:
            reasons.append("Proposed notional exceeds the maximum position size.")
        if context.account_exposure + context.proposed_notional > context.max_account_exposure:
            reasons.append("Projected account exposure exceeds the account exposure limit.")
        if context.daily_pnl <= -abs(context.daily_loss_limit):
            reasons.append("The configured daily loss limit has been reached.")
        if context.current_drawdown >= context.max_drawdown_limit:
            reasons.append("The configured maximum drawdown has been reached.")
    if proposed_side == "none":
        reasons.append("There is no actionable strategy proposal.")
    return RiskManagerOutput(
        allowed=not reasons,
        veto_reasons=reasons,
        checked_at=checked_time,
        policy_version=POLICY_VERSION,
    )


def resolve_debate(
    assessments: dict[str, AnalystOutput],
    evidence_sources: dict[str, str],
    strategy_direction: Direction,
    risk: RiskManagerOutput,
) -> DebateDecision:
    """Resolve with independent-source quorum, not an agent-count majority.

    At least two distinct analyst roles and two distinct evidence sources are
    required. A strategy proposal must match the candidate; supporting sources
    must outnumber opposing sources by at least 2:1. Evidence IDs are deduped
    by source, preventing repeated references to one source from inflating
    support. The thresholds are workflow policy, not validated trading alpha.
    """
    (
        candidate,
        quorum_met,
        supporting,
        opposing,
        participating,
        leading_direction,
    ) = choose_candidate(assessments, evidence_sources)
    if candidate != "abstain" and candidate != strategy_direction:
        candidate = "abstain"

    if not risk.allowed:
        status = "vetoed"
        rationale = (
            "Deterministic Risk Manager veto: "
            + "; ".join(risk.veto_reasons)
            + f" Evidence debate retained: {len(supporting)} supporting and "
            + f"{len(opposing)} opposing independent source(s)."
        )
        decision_direction: Direction = "abstain"
    elif not quorum_met:
        status = "insufficient_evidence"
        rationale = (
            "Quorum not met: two analyst roles and two independent sources are required. "
            f"Current leading signal: {leading_direction}; {len(supporting)} supporting and "
            f"{len(opposing)} opposing independent source(s)."
        )
        decision_direction = "abstain"
    elif candidate == "abstain":
        status = "disagreement"
        rationale = (
            f"Disagreement preserved: leading evidence points {leading_direction} with "
            f"{len(supporting)} supporting and {len(opposing)} opposing independent source(s); "
            "the 2:1 source margin or Strategy proposal requirement was not met."
        )
        decision_direction = "abstain"
    else:
        status = "consensus"
        rationale = (
            f"{len(supporting)} independent source(s) support {candidate}; "
            f"{len(opposing)} independent source(s) oppose it."
        )
        decision_direction = candidate
    return DebateDecision(
        direction=decision_direction,
        status=status,
        quorum_met=quorum_met,
        supporting_sources=sorted(supporting),
        opposing_sources=sorted(opposing),
        participating_agents=sorted(participating),
        evidence_ids=sorted(
            {
                evidence_id
                for agent in participating
                for evidence_id in assessments[agent].evidence_ids
                if evidence_id in evidence_sources
            }
        ),
        rationale=rationale,
        risk=risk,
    )


def choose_candidate(
    assessments: dict[str, AnalystOutput],
    evidence_sources: dict[str, str],
) -> tuple[Direction, bool, set[str], set[str], list[str], Direction]:
    source_votes: dict[Direction, set[str]] = {
        "bullish": set(),
        "bearish": set(),
        "neutral": set(),
        "abstain": set(),
    }
    participating: list[str] = []
    for agent, output in assessments.items():
        if agent not in ANALYSTS or output.status != "completed":
            continue
        valid_sources = {
            evidence_sources[evidence_id]
            for evidence_id in output.evidence_ids
            if evidence_id in evidence_sources
        }
        if not valid_sources or output.direction == "abstain":
            continue
        participating.append(agent)
        source_votes[output.direction].update(valid_sources)

    participating_sources = set().union(
        *(source_votes[direction] for direction in source_votes if direction != "abstain")
    )
    quorum_met = len(participating) >= 2 and len(participating_sources) >= 2
    candidate: Direction = "abstain"
    supporting: set[str] = set()
    opposing: set[str] = set()
    leading_direction: Direction = "abstain"
    if quorum_met:
        candidates = sorted(
            (direction for direction in ("bullish", "bearish", "neutral")),
            key=lambda direction: len(source_votes[direction]),
            reverse=True,
        )
        for direction in candidates:
            contrary = set().union(
                *(
                    source_votes[other]
                    for other in ("bullish", "bearish", "neutral")
                    if other != direction
                )
            )
            aligned = source_votes[direction]
            if leading_direction == "abstain" and aligned:
                leading_direction = direction
                supporting = aligned
                opposing = contrary
            if (
                len(aligned) >= 2
                and len(aligned) >= 2 * len(contrary) + 1
            ):
                candidate = direction
                supporting = aligned
                opposing = contrary
                break
    elif participating_sources:
        leading_direction = max(
            ("bullish", "bearish", "neutral"),
            key=lambda direction: len(source_votes[direction]),
        )
        supporting = source_votes[leading_direction]
        opposing = set().union(
            *(
                source_votes[other]
                for other in ("bullish", "bearish", "neutral")
                if other != leading_direction
            )
        )
    return candidate, quorum_met, supporting, opposing, participating, leading_direction
