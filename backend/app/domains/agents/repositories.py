from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.agents.models import (
    AgentCommunication,
    AgentDecision,
    AgentEvaluation,
    AgentEvent,
    AgentOutcome,
    AgentPaperExecution,
    AgentRun,
    AgentSimulation,
    AgentStrategyVersion,
    AgentTelemetry,
    AgentTuningProposal,
)


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(self, owner_id: str, symbol: str, interval: str) -> AgentRun:
        run = AgentRun(
            owner_id=owner_id,
            symbol=symbol.upper(),
            interval=interval,
            status="queued",
            input_payload={"symbol": symbol.upper(), "interval": interval},
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: UUID, owner_id: str | None = None) -> AgentRun | None:
        statement = select(AgentRun).where(AgentRun.id == run_id)
        if owner_id is not None:
            statement = statement.where(AgentRun.owner_id == owner_id)
        return await self.session.scalar(statement)

    async def list_runs(self, owner_id: str, limit: int = 50) -> list[AgentRun]:
        statement = (
            select(AgentRun)
            .where(AgentRun.owner_id == owner_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_recoverable_runs(self) -> list[AgentRun]:
        statement = select(AgentRun).where(AgentRun.status.in_(("queued", "running")))
        return list((await self.session.scalars(statement)).all())

    async def add_event(
        self,
        run_id: UUID,
        event_type: str,
        *,
        agent: str | None = None,
        node: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        sequence = await self.session.scalar(
            select(func.coalesce(func.max(AgentEvent.sequence), 0)).where(
                AgentEvent.run_id == run_id
            )
        )
        event = AgentEvent(
            run_id=run_id,
            sequence=(sequence or 0) + 1,
            event_type=event_type,
            agent=agent,
            node=node,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_events(self, run_id: UUID) -> list[AgentEvent]:
        statement = (
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id)
            .order_by(AgentEvent.sequence)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_communications(self, run_id: UUID) -> list[AgentCommunication]:
        statement = (
            select(AgentCommunication)
            .where(AgentCommunication.run_id == run_id)
            .order_by(AgentCommunication.created_at)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_telemetry(self, run_id: UUID) -> list[AgentTelemetry]:
        statement = (
            select(AgentTelemetry)
            .where(AgentTelemetry.run_id == run_id)
            .order_by(AgentTelemetry.created_at)
        )
        return list((await self.session.scalars(statement)).all())

    async def get_decisions(self, run_id: UUID) -> list[AgentDecision]:
        statement = (
            select(AgentDecision)
            .where(AgentDecision.run_id == run_id)
            .order_by(AgentDecision.created_at)
        )
        return list((await self.session.scalars(statement)).all())

    async def add_communication(
        self, run_id: UUID, sender: str, recipient: str, message: dict[str, Any]
    ) -> None:
        self.session.add(
            AgentCommunication(
                run_id=run_id,
                sender=sender,
                recipient=recipient,
                message=message,
            )
        )
        await self.session.flush()

    async def add_telemetry(
        self,
        run_id: UUID,
        agent: str,
        status: str,
        *,
        model: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        api_cost: float | None = None,
        retries: int = 0,
        failure_details: str | None = None,
    ) -> None:
        self.session.add(
            AgentTelemetry(
                run_id=run_id,
                agent=agent,
                model=model,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                api_cost=api_cost,
                retries=retries,
                status=status,
                failure_details=failure_details,
            )
        )
        await self.session.flush()

    async def add_decision(
        self,
        run_id: UUID,
        symbol: str,
        direction: str,
        status: str,
        rationale: str,
        evidence: list[dict[str, Any]],
        *,
        agent: str = "consensus",
        confidence: float | None = None,
        strategy_version_id: UUID | None = None,
    ) -> AgentDecision:
        existing = await self.session.scalar(
            select(AgentDecision).where(
                AgentDecision.run_id == run_id,
                AgentDecision.agent == agent,
            )
        )
        if existing is not None:
            existing.direction = direction
            existing.status = status
            existing.rationale = rationale
            existing.evidence = evidence
            existing.confidence = confidence
            existing.strategy_version_id = strategy_version_id
            await self.session.flush()
            return existing
        decision = AgentDecision(
            run_id=run_id,
            agent=agent,
            symbol=symbol,
            direction=direction,
            status=status,
            rationale=rationale,
            evidence=evidence,
            confidence=confidence,
            strategy_version_id=strategy_version_id,
        )
        self.session.add(decision)
        await self.session.flush()
        return decision

    async def add_outcome(self, outcome: AgentOutcome) -> None:
        self.session.add(outcome)
        await self.session.flush()

    async def add_paper_execution(
        self,
        run_id: UUID,
        decision_id: UUID,
        status: str,
        result: dict[str, Any],
        *,
        paper_order_id: str | None,
        executed_at: Any = None,
    ) -> None:
        self.session.add(
            AgentPaperExecution(
                run_id=run_id,
                decision_id=decision_id,
                status=status,
                result=result,
                paper_order_id=paper_order_id,
                executed_at=executed_at,
            )
        )
        await self.session.flush()

    async def get_simulations(self, owner_id: str, limit: int = 50) -> list[AgentSimulation]:
        statement = (
            select(AgentSimulation)
            .where(AgentSimulation.owner_id == owner_id)
            .order_by(AgentSimulation.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def create_tuning_proposal(
        self,
        owner_id: str,
        base_strategy_version_id: UUID,
        candidate_parameters: dict[str, Any],
    ) -> AgentTuningProposal:
        proposal = AgentTuningProposal(
            owner_id=owner_id,
            base_strategy_version_id=base_strategy_version_id,
            candidate_parameters=candidate_parameters,
            status="draft",
        )
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def get_tuning_proposal(
        self,
        proposal_id: UUID,
        owner_id: str,
    ) -> AgentTuningProposal | None:
        statement = select(AgentTuningProposal).where(
            AgentTuningProposal.id == proposal_id,
            AgentTuningProposal.owner_id == owner_id,
        )
        return await self.session.scalar(statement)

    async def get_simulation(
        self,
        simulation_id: UUID,
        owner_id: str,
    ) -> AgentSimulation | None:
        statement = select(AgentSimulation).where(
            AgentSimulation.id == simulation_id,
            AgentSimulation.owner_id == owner_id,
        )
        return await self.session.scalar(statement)

    async def list_tuning_proposals(self, owner_id: str) -> list[AgentTuningProposal]:
        statement = (
            select(AgentTuningProposal)
            .where(AgentTuningProposal.owner_id == owner_id)
            .order_by(AgentTuningProposal.created_at.desc())
            .limit(50)
        )
        return list((await self.session.scalars(statement)).all())

    async def add_evaluation(
        self,
        owner_id: str,
        agent: str,
        metrics: dict[str, Any],
        version: str,
    ) -> None:
        self.session.add(
            AgentEvaluation(
                owner_id=owner_id,
                agent=agent,
                metrics=metrics,
                methodology_version=version,
            )
        )
        await self.session.flush()

    async def get_latest_evaluations(self, owner_id: str) -> dict[str, dict[str, Any]]:
        statement = (
            select(AgentEvaluation)
            .where(AgentEvaluation.owner_id == owner_id)
            .order_by(AgentEvaluation.created_at.desc())
        )
        rows = list((await self.session.scalars(statement)).all())
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:
            latest.setdefault(row.agent, row.metrics)
        return latest

    async def get_approved_strategy(self, owner_id: str) -> AgentStrategyVersion | None:
        statement = (
            select(AgentStrategyVersion)
            .where(
                AgentStrategyVersion.owner_id == owner_id,
                AgentStrategyVersion.status == "approved",
            )
            .order_by(AgentStrategyVersion.approved_at.desc())
            .limit(1)
        )
        return await self.session.scalar(statement)

    async def get_verified_observations(
        self,
        agent: str,
        owner_id: str,
    ) -> list[dict[str, object]]:
        statement = (
            select(
                AgentDecision.direction,
                AgentOutcome.decision_id,
                AgentOutcome.verified,
                AgentOutcome.source,
                AgentOutcome.observed_at,
                AgentOutcome.realized_return,
                AgentOutcome.direction_correct,
                AgentOutcome.confidence,
                AgentOutcome.rule_adherent,
                AgentOutcome.condition_key,
            )
            .select_from(AgentDecision)
            .join(AgentOutcome, AgentOutcome.decision_id == AgentDecision.id)
            .join(AgentRun, AgentRun.id == AgentDecision.run_id)
            .where(
                AgentDecision.agent == agent,
                AgentRun.owner_id == owner_id,
                AgentOutcome.verified.is_(True),
                AgentOutcome.direction_correct.is_not(None),
            )
        )
        rows = (await self.session.execute(statement)).all()
        return [
            {
                "direction": direction,
                "decision_id": decision_id,
                "verified": verified,
                "source": source,
                "observed_at": observed_at,
                "realized_return": float(realized_return) if realized_return is not None else None,
                "direction_correct": direction_correct,
                "confidence": float(confidence) if confidence is not None else None,
                "rule_adherent": rule_adherent,
                "condition_key": condition_key,
            }
            for (
                direction,
                decision_id,
                verified,
                source,
                observed_at,
                realized_return,
                direction_correct,
                confidence,
                rule_adherent,
                condition_key,
            ) in rows
        ]

    async def get_strategy_version(self, version_id: UUID) -> AgentStrategyVersion | None:
        return await self.session.get(AgentStrategyVersion, version_id)
