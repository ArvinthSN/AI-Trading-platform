"""Persist agent runs, evidence, telemetry, and verified outcomes.

Revision ID: 20261121_02
Revises: 20261121_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261121_02"
down_revision: str | None = "20261121_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_node", sa.String(80)),
        sa.Column("input_payload", _json(), nullable=False),
        sa.Column("result_payload", _json()),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_symbol", "agent_runs", ["symbol"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_owner_id", "agent_runs", ["owner_id"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("agent", sa.String(30)),
        sa.Column("node", sa.String(80)),
        sa.Column("payload", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_event_run_sequence"),
    )
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])

    op.create_table(
        "agent_communications",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("sender", sa.String(30), nullable=False),
        sa.Column("recipient", sa.String(30), nullable=False),
        sa.Column("message", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_communications_run_id", "agent_communications", ["run_id"])

    op.create_table(
        "agent_telemetry",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent", sa.String(30), nullable=False),
        sa.Column("model", sa.String(120)),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("api_cost", sa.Numeric(14, 8)),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_details", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_telemetry_run_id", "agent_telemetry", ["run_id"])

    op.create_table(
        "agent_strategy_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("parameters", _json(), nullable=False),
        sa.Column("validation", _json()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "name",
            "version",
            name="uq_agent_strategy_owner_name_version",
        ),
    )
    op.create_index(
        "ix_agent_strategy_versions_owner_id",
        "agent_strategy_versions",
        ["owner_id"],
    )

    op.create_table(
        "agent_decisions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("agent", sa.String(30), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(as_uuid=True)),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rationale", sa.String(2000), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("evidence", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"],
            ["agent_strategy_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "agent", name="uq_agent_decision_run_agent"),
    )
    op.create_index("ix_agent_decisions_run_id", "agent_decisions", ["run_id"])
    op.create_index("ix_agent_decisions_agent", "agent_decisions", ["agent"])

    op.create_table(
        "agent_outcomes",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("decision_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("realized_return", sa.Numeric(18, 8)),
        sa.Column("direction_correct", sa.Boolean()),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("rule_adherent", sa.Boolean()),
        sa.Column("condition_key", sa.String(200)),
        sa.ForeignKeyConstraint(["decision_id"], ["agent_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_outcomes_decision_id", "agent_outcomes", ["decision_id"])

    op.create_table(
        "agent_evaluations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("agent", sa.String(30), nullable=False),
        sa.Column("metrics", _json(), nullable=False),
        sa.Column("methodology_version", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_evaluations_agent", "agent_evaluations", ["agent"])
    op.create_index(
        "ix_agent_evaluations_owner_id",
        "agent_evaluations",
        ["owner_id"],
    )

    op.create_table(
        "agent_paper_executions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("decision_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("paper_order_id", sa.String(160)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", _json(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decision_id"], ["agent_decisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paper_order_id", name="uq_agent_paper_order_id"),
    )
    op.create_index("ix_agent_paper_executions_run_id", "agent_paper_executions", ["run_id"])
    op.create_index(
        "ix_agent_paper_executions_decision_id",
        "agent_paper_executions",
        ["decision_id"],
    )

    op.create_table(
        "agent_simulations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_payload", _json(), nullable=False),
        sa.Column("result_payload", _json()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('scenario', 'backtest')", name="ck_agent_simulation_kind"),
    )
    op.create_index("ix_agent_simulations_owner_id", "agent_simulations", ["owner_id"])

    op.create_table(
        "agent_tuning_proposals",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("base_strategy_version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("candidate_parameters", _json(), nullable=False),
        sa.Column("validation", _json()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("approved_by", sa.String(255)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["base_strategy_version_id"],
            ["agent_strategy_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tuning_proposals_owner_id", "agent_tuning_proposals", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_tuning_proposals_owner_id", table_name="agent_tuning_proposals")
    op.drop_table("agent_tuning_proposals")
    op.drop_index("ix_agent_simulations_owner_id", table_name="agent_simulations")
    op.drop_table("agent_simulations")
    op.drop_index("ix_agent_paper_executions_decision_id", table_name="agent_paper_executions")
    op.drop_index("ix_agent_paper_executions_run_id", table_name="agent_paper_executions")
    op.drop_table("agent_paper_executions")
    op.drop_index("ix_agent_evaluations_owner_id", table_name="agent_evaluations")
    op.drop_index("ix_agent_evaluations_agent", table_name="agent_evaluations")
    op.drop_table("agent_evaluations")
    op.drop_index("ix_agent_outcomes_decision_id", table_name="agent_outcomes")
    op.drop_table("agent_outcomes")
    op.drop_index("ix_agent_decisions_agent", table_name="agent_decisions")
    op.drop_index("ix_agent_decisions_run_id", table_name="agent_decisions")
    op.drop_table("agent_decisions")
    op.drop_index("ix_agent_strategy_versions_owner_id", table_name="agent_strategy_versions")
    op.drop_table("agent_strategy_versions")
    op.drop_index("ix_agent_telemetry_run_id", table_name="agent_telemetry")
    op.drop_table("agent_telemetry")
    op.drop_index("ix_agent_communications_run_id", table_name="agent_communications")
    op.drop_table("agent_communications")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_owner_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_symbol", table_name="agent_runs")
    op.drop_table("agent_runs")
