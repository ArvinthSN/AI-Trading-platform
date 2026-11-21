from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

JsonValue = JSON().with_variant(JSONB, "postgresql")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    current_node: Mapped[str | None] = mapped_column(String(80))
    input_payload: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonValue)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AgentEvent(Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    agent: Mapped[str | None] = mapped_column(String(30))
    node: Mapped[str | None] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentCommunication(Base):
    __tablename__ = "agent_communications"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentTelemetry(Base):
    __tablename__ = "agent_telemetry"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    agent: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    api_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 8))
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    failure_details: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentStrategyVersion(Base):
    __tablename__ = "agent_strategy_versions"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "name",
            "version",
            name="uq_agent_strategy_owner_name_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JsonValue)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentDecision(Base):
    __tablename__ = "agent_decisions"
    __table_args__ = (
        UniqueConstraint("run_id", "agent", name="uq_agent_decision_run_agent"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    strategy_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_strategy_versions.id", ondelete="SET NULL")
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JsonValue, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    outcomes: Mapped[list["AgentOutcome"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class AgentOutcome(Base):
    __tablename__ = "agent_outcomes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_decisions.id", ondelete="CASCADE"), nullable=False
    )
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    realized_return: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    direction_correct: Mapped[bool | None] = mapped_column(Boolean)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    rule_adherent: Mapped[bool | None] = mapped_column(Boolean)
    condition_key: Mapped[str | None] = mapped_column(String(200))
    decision: Mapped[AgentDecision] = relationship(back_populates="outcomes")


class AgentEvaluation(Base):
    __tablename__ = "agent_evaluations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentPaperExecution(Base):
    __tablename__ = "agent_paper_executions"
    __table_args__ = (
        UniqueConstraint("paper_order_id", name="uq_agent_paper_order_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_decisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    paper_order_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentSimulation(Base):
    __tablename__ = "agent_simulations"
    __table_args__ = (
        CheckConstraint("kind IN ('scenario', 'backtest')", name="ck_agent_simulation_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonValue)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentTuningProposal(Base):
    __tablename__ = "agent_tuning_proposals"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_strategy_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_strategy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    candidate_parameters: Mapped[dict[str, Any]] = mapped_column(JsonValue, nullable=False)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JsonValue)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(255))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
