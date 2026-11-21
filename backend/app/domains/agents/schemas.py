from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

AgentName = Literal[
    "fundamental",
    "sentiment",
    "technical",
    "strategy",
    "risk_manager",
    "execution",
    "performance_critic",
]
Direction = Literal["bullish", "bearish", "neutral", "abstain"]
RunStatus = Literal[
    "queued",
    "running",
    "paused",
    "completed",
    "failed",
    "cancelled",
    "unavailable",
]


class Evidence(BaseModel):
    id: str
    source: str
    observed_at: datetime
    content: str
    url: HttpUrl | None = None


class AgentInput(BaseModel):
    run_id: UUID
    symbol: str
    evidence: list[Evidence] = Field(default_factory=list)


class AnalystOutput(BaseModel):
    status: Literal["completed", "abstained", "unavailable", "failed"]
    direction: Direction
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    diagnostics: str | None = None
    generated_at: datetime


class FundamentalAgentInput(AgentInput):
    """Verified issuer, protocol, and macro evidence; no price-only inference."""


class FundamentalAgentOutput(AnalystOutput):
    agent: Literal["fundamental"] = "fundamental"


class SentimentAgentInput(AgentInput):
    """Timestamped, source-backed news and sentiment-provider observations."""


class SentimentAgentOutput(AnalystOutput):
    agent: Literal["sentiment"] = "sentiment"


class TechnicalSnapshot(BaseModel):
    close: float
    ema: dict[int, float | None]
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    adx: float | None
    observed_at: datetime
    source: str


class TechnicalAgentInput(AgentInput):
    snapshot: TechnicalSnapshot


class TechnicalAgentOutput(AnalystOutput):
    agent: Literal["technical"] = "technical"


class StrategyVersion(BaseModel):
    id: UUID
    name: str
    version: str
    parameters: dict[str, float | int | str | bool]
    approved: bool


class StrategyAgentInput(AgentInput):
    """Translate sufficiently supported analyst evidence into a versioned proposal."""

    assessments: list[AnalystOutput]
    strategy_version: StrategyVersion | None = None


class StrategyAgentOutput(AnalystOutput):
    agent: Literal["strategy"] = "strategy"
    proposed_side: Literal["long", "short", "none"] = "none"


class RiskContext(BaseModel):
    account_connected: bool
    account_exposure: float | None = None
    max_account_exposure: float | None = None
    proposed_notional: float | None = None
    max_position_size: float | None = None
    daily_pnl: float | None = None
    daily_loss_limit: float | None = None
    current_drawdown: float | None = None
    max_drawdown_limit: float | None = None
    observed_at: datetime | None = None


class RiskManagerInput(AgentInput):
    """Apply configured account limits without consulting model-generated decisions."""

    context: RiskContext
    proposed_side: Literal["long", "short", "none"]


class RiskManagerOutput(BaseModel):
    agent: Literal["risk_manager"] = "risk_manager"
    allowed: bool
    veto_reasons: list[str]
    checked_at: datetime
    policy_version: str


class DebateDecision(BaseModel):
    direction: Direction
    status: Literal["consensus", "disagreement", "insufficient_evidence", "vetoed"]
    quorum_met: bool
    supporting_sources: list[str]
    opposing_sources: list[str]
    participating_agents: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str
    risk: RiskManagerOutput | None = None


class ExecutionAgentInput(AgentInput):
    """Submit an approved decision only to the NEXTRADE paper-trading engine."""

    decision: DebateDecision
    strategy_version: StrategyVersion | None = None


class ExecutionAgentOutput(BaseModel):
    agent: Literal["execution"] = "execution"
    status: Literal["accepted", "rejected", "unavailable", "failed"]
    engine: Literal["nextrade_paper_trading"]
    paper_order_id: str | None = None
    reason: str | None = None
    executed_at: datetime | None = None


class VerifiedOutcome(BaseModel):
    decision_id: UUID
    verified: bool
    source: str
    observed_at: datetime
    realized_return: float | None = None
    direction_correct: bool | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    rule_adherent: bool | None = None
    condition_key: str | None = None


class PerformanceCriticInput(AgentInput):
    """Evaluate historical decisions using verified outcomes only."""

    verified_outcomes: list[VerifiedOutcome]
    historical_assessments: list[AnalystOutput]


class PerformanceMetrics(BaseModel):
    verified_sample_size: int
    accuracy: float | None
    confidence_calibration_error: float | None
    rule_adherence: float | None
    consistency: float | None
    intelligence_score: float | None
    methodology_version: str


class PerformanceCriticOutput(BaseModel):
    agent: Literal["performance_critic"] = "performance_critic"
    status: Literal["completed", "insufficient_verified_data"]
    metrics: PerformanceMetrics
    evaluated_at: datetime


class AgentRunCreate(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9-]{5,30}$")
    interval: str = Field(default="1h", pattern=r"^(1m|5m|15m|1h|4h|1d)$")


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    interval: str
    status: RunStatus
    current_node: str | None
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class AgentEventResponse(BaseModel):
    sequence: int
    event_type: str
    agent: str | None = None
    node: str | None = None
    payload: dict[str, object]
    created_at: datetime


class AgentTelemetryResponse(BaseModel):
    agent: str
    model: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    api_cost: float | None
    retries: int
    status: str
    failure_details: str | None
    created_at: datetime


class AgentCommunicationResponse(BaseModel):
    sender: str
    recipient: str
    message: dict[str, object]
    created_at: datetime


class AgentObservabilityResponse(BaseModel):
    run_id: UUID
    events: list[AgentEventResponse]
    telemetry: list[AgentTelemetryResponse]
    communications: list[AgentCommunicationResponse]


class AgentSimulationResponse(BaseModel):
    id: UUID
    kind: Literal["scenario", "backtest"]
    status: str
    input_payload: dict[str, object]
    result_payload: dict[str, object] | None
    created_at: datetime


class AgentTuningProposalCreate(BaseModel):
    base_strategy_version_id: UUID
    candidate_parameters: dict[str, float | int | str | bool]


class StrategyVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=40)
    parameters: dict[str, float | int | str | bool]


class ScenarioSimulationRequest(BaseModel):
    kind: Literal["scenario", "backtest"]
    symbol: str = Field(pattern=r"^[A-Za-z0-9-]{5,30}$")
    parameters: dict[str, float | int | str | bool]


class AgentTuningProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    base_strategy_version_id: UUID
    candidate_parameters: dict[str, object]
    validation: dict[str, object] | None
    status: str
    approved_by: str | None
    approved_at: datetime | None
    applied_at: datetime | None
    created_at: datetime


class AgentRosterEntry(BaseModel):
    agent: AgentName
    status: Literal[
        "not_started",
        "running",
        "completed",
        "failed",
        "unavailable",
        "paused",
        "cancelled",
        "vetoed",
        "rejected",
        "insufficient_verified_data",
        "abstained",
        "accepted",
    ]
    last_run_at: datetime | None = None
    detail: str | None = None


class AgentDashboardResponse(BaseModel):
    status: Literal["available", "unavailable"]
    runs: list[AgentRunResponse]
    agents: list[AgentRosterEntry]
    latest_decision: DebateDecision | None = None
    latest_execution: ExecutionAgentOutput | None = None
    latest_evidence: list[Evidence] = Field(default_factory=list)
    latest_events: list[AgentEventResponse] = Field(default_factory=list)
    performance: dict[str, PerformanceMetrics] = Field(default_factory=dict)
    reason: str | None = None
