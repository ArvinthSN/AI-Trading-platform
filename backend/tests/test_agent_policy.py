from datetime import UTC, datetime

from app.domains.agents.policy import deterministic_risk_check, resolve_debate
from app.domains.agents.schemas import AnalystOutput, Direction, RiskContext, RiskManagerOutput

AT = datetime(2026, 11, 21, tzinfo=UTC)


def analyst(direction: Direction, *evidence_ids: str) -> AnalystOutput:
    return AnalystOutput(
        status="completed",
        direction=direction,
        rationale="Evidence summary.",
        evidence_ids=list(evidence_ids),
        generated_at=AT,
    )


def allowed_risk() -> RiskManagerOutput:
    return RiskManagerOutput(
        allowed=True,
        veto_reasons=[],
        checked_at=AT,
        policy_version="evidence-quorum-v1",
    )


def test_debate_requires_independent_source_quorum_and_strategy_alignment() -> None:
    decision = resolve_debate(
        {
            "technical": analyst("bullish", "e1"),
            "fundamental": analyst("bullish", "e2"),
            "sentiment": analyst("bearish", "e3"),
        },
        {"e1": "source-a", "e2": "source-b", "e3": "source-c"},
        "bullish",
        allowed_risk(),
    )

    assert decision.status == "disagreement"
    assert decision.direction == "abstain"
    assert decision.supporting_sources == ["source-a", "source-b"]
    assert decision.opposing_sources == ["source-c"]
    assert "Disagreement preserved" in decision.rationale


def test_debate_deduplicates_sources_instead_of_counting_agent_votes() -> None:
    decision = resolve_debate(
        {
            "technical": analyst("bullish", "e1"),
            "fundamental": analyst("bullish", "e2"),
            "sentiment": analyst("bearish", "e3"),
        },
        {"e1": "same-source", "e2": "same-source", "e3": "other-source"},
        "bullish",
        allowed_risk(),
    )

    assert decision.quorum_met
    assert decision.status == "disagreement"
    assert decision.direction == "abstain"


def test_risk_manager_vetoes_missing_context_independently_of_debate() -> None:
    risk = deterministic_risk_check(
        RiskContext(account_connected=False),
        "long",
        checked_at=AT,
    )
    decision = resolve_debate(
        {
            "technical": analyst("bullish", "e1"),
            "fundamental": analyst("bullish", "e2"),
        },
        {"e1": "source-a", "e2": "source-b"},
        "bullish",
        risk,
    )

    assert not risk.allowed
    assert decision.status == "vetoed"
    assert decision.direction == "abstain"


def test_risk_manager_vetoes_limit_breaches() -> None:
    risk = deterministic_risk_check(
        RiskContext(
            account_connected=True,
            account_exposure=80,
            max_account_exposure=100,
            proposed_notional=30,
            max_position_size=100,
            daily_pnl=-50,
            daily_loss_limit=50,
            current_drawdown=0.1,
            max_drawdown_limit=0.2,
            observed_at=AT,
        ),
        "long",
        checked_at=AT,
    )

    assert not risk.allowed
    assert "Projected account exposure exceeds the account exposure limit." in risk.veto_reasons
    assert "The configured daily loss limit has been reached." in risk.veto_reasons


def test_evidence_weighted_policy_can_reach_consensus_without_agent_vote_counting() -> None:
    decision = resolve_debate(
        {
            "technical": analyst("bullish", "e1"),
            "fundamental": analyst("bullish", "e2", "e3"),
            "sentiment": analyst("bearish", "e4"),
        },
        {
            "e1": "source-a",
            "e2": "source-b",
            "e3": "source-c",
            "e4": "source-d",
        },
        "bullish",
        allowed_risk(),
    )

    assert decision.status == "consensus"
    assert decision.direction == "bullish"
    assert decision.supporting_sources == ["source-a", "source-b", "source-c"]
    assert decision.opposing_sources == ["source-d"]
