import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID

import httpx
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.research import (
    OpenAIResearchProvider,
    ResearchEvidence,
    ResearchExecution,
)
from app.domains.agents.performance import EvaluationObservation, evaluate_performance
from app.domains.agents.policy import choose_candidate, deterministic_risk_check, resolve_debate
from app.domains.agents.repositories import AgentRepository
from app.domains.agents.schemas import (
    AnalystOutput,
    DebateDecision,
    Evidence,
    ExecutionAgentInput,
    ExecutionAgentOutput,
    FundamentalAgentInput,
    FundamentalAgentOutput,
    PerformanceCriticInput,
    PerformanceCriticOutput,
    RiskContext,
    RiskManagerInput,
    RiskManagerOutput,
    SentimentAgentInput,
    SentimentAgentOutput,
    StrategyAgentInput,
    StrategyAgentOutput,
    StrategyVersion,
    TechnicalAgentInput,
    TechnicalAgentOutput,
    TechnicalSnapshot,
    VerifiedOutcome,
)
from app.domains.agents.services.events import AgentEventHub
from app.domains.agents.services.paper_execution import (
    HttpPaperTradingEngine,
    PaperOrderRequest,
)
from app.domains.market.indicators.service import calculate_indicators
from app.domains.market.router.provider_router import ProviderRouter
from app.domains.market.schemas.market import IndicatorParameters
from app.domains.market.services.candle_cache import candle_is_fresh

logger = logging.getLogger(__name__)
AGENT_NAMES = (
    "fundamental",
    "sentiment",
    "technical",
    "strategy",
    "risk_manager",
    "execution",
    "performance_critic",
)
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class AgentState(TypedDict, total=False):
    run_id: str
    owner_id: str
    symbol: str
    interval: str
    candles: list[dict[str, Any]]
    provider: str
    technical_snapshot: dict[str, Any]
    evidence: list[dict[str, Any]]
    evidence_sources: dict[str, str]
    assessments: dict[str, dict[str, Any]]
    strategy_version: dict[str, Any] | None
    strategy: dict[str, Any]
    risk_context: dict[str, Any]
    risk: dict[str, Any]
    decision: dict[str, Any]
    decision_id: str
    execution: dict[str, Any]
    evaluations: dict[str, dict[str, Any]]
    performance: dict[str, Any]
    cancelled: bool


NodeOperation = Callable[[AgentState], Awaitable[dict[str, Any]]]


class AgentOrchestrator:
    def __init__(
        self,
        market_router: ProviderRouter,
        http_client: httpx.AsyncClient,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        checkpointer: BaseCheckpointSaver,
        event_hub: AgentEventHub,
    ) -> None:
        self._market_router = market_router
        self._session_factory = session_factory
        self._event_hub = event_hub
        self._settings = settings
        self._paper_engine = HttpPaperTradingEngine(http_client, settings)
        self._research_provider = (
            OpenAIResearchProvider(settings)
            if settings.openai_api_key and settings.openai_model
            else None
        )
        self._research_chain = RunnableLambda(self._invoke_research)
        self._checkpointer = checkpointer
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._tasks_lock = asyncio.Lock()
        self._graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)
        nodes: list[tuple[str, NodeOperation]] = [
            ("market_data", self._market_data),
            ("fundamental", self._fundamental),
            ("sentiment", self._sentiment),
            ("technical", self._technical),
            ("strategy", self._strategy),
            ("risk_manager", self._risk_manager),
            ("execution", self._execution),
            ("performance_critic", self._performance_critic),
        ]
        for name, operation in nodes:
            builder.add_node(name, self._wrap_node(name, operation))
        builder.set_entry_point(nodes[0][0])
        for (name, _), (next_name, _) in zip(nodes, nodes[1:], strict=False):
            builder.add_conditional_edges(
                name,
                lambda state: "cancel" if state.get("cancelled") else "continue",
                {"continue": next_name, "cancel": END},
            )
        builder.add_edge(nodes[-1][0], END)
        return builder.compile(checkpointer=self._checkpointer)

    async def start(self, run_id: UUID, *, resume: bool = False, recover: bool = False) -> None:
        async with self._tasks_lock:
            current = self._tasks.get(run_id)
            if current is not None and not current.done():
                return
            self._tasks[run_id] = asyncio.create_task(
                self._run(run_id, resume=resume, recover=recover),
                name=f"agent-run-{run_id}",
            )

    async def recover(self) -> None:
        async with self._session_factory() as session:
            runs = await AgentRepository(session).list_recoverable_runs()
            resumable = [(run.id, run.status == "running") for run in runs]
        for run_id, resume_from_checkpoint in resumable:
            await self.start(run_id, recover=resume_from_checkpoint)

    async def pause(self, run_id: UUID, owner_id: str) -> None:
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id, owner_id)
            if run is None:
                raise LookupError("Agent run not found.")
            if run.status not in {"queued", "running"}:
                raise ValueError(f"Cannot pause an agent run in state {run.status}.")
            run.status = "paused"
            await repository.add_event(run_id, "pause_requested", payload={})
            await session.commit()
        await self._publish(run, "pause_requested", {})
        task = self._tasks.get(run_id)
        if task is not None and not task.done():
            await task

    async def resume(self, run_id: UUID, owner_id: str) -> None:
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id, owner_id)
            if run is None:
                raise LookupError("Agent run not found.")
            if run.status != "paused":
                raise ValueError(f"Cannot resume an agent run in state {run.status}.")
            run.status = "running"
            await repository.add_event(run_id, "resume_requested", payload={})
            await session.commit()
        await self._publish(run, "resume_requested", {})
        await self.start(run_id, resume=True)

    async def cancel(self, run_id: UUID, owner_id: str) -> None:
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id, owner_id)
            if run is None:
                raise LookupError("Agent run not found.")
            if run.status in {"completed", "failed", "cancelled"}:
                raise ValueError(f"Cannot cancel an agent run in state {run.status}.")
            run.cancel_requested = True
            if run.status in {"queued", "paused"}:
                run.status = "cancelled"
            await repository.add_event(run_id, "cancel_requested", payload={})
            await session.commit()
        await self._publish(run, "cancel_requested", {})

    async def _run(self, run_id: UUID, *, resume: bool, recover: bool) -> None:
        async with self._session_factory() as session:
            run = await AgentRepository(session).get_run(run_id)
            if run is None:
                return
            initial: AgentState = {
                "run_id": str(run.id),
                "owner_id": run.owner_id,
                "symbol": run.symbol,
                "interval": run.interval,
            }
        config = {"configurable": {"thread_id": str(run_id)}}
        try:
            if resume:
                command: Any = Command(resume=True)
            elif recover:
                checkpoint = await self._graph.aget_state(config)
                command = None if checkpoint.values else initial
            else:
                command = initial
            result = await self._graph.ainvoke(command, config=config)
            if result.get("__interrupt__"):
                await self._set_terminal(run_id, "paused", result)
            elif result.get("cancelled"):
                await self._set_terminal(run_id, "cancelled", result)
            else:
                await self._set_terminal(run_id, "completed", result)
        except Exception as error:
            logger.exception(
                "agent_workflow_failed run_id=%s error_type=%s",
                run_id,
                type(error).__name__,
            )
            await self._set_terminal(
                run_id,
                "failed",
                {"error": type(error).__name__},
                error=type(error).__name__,
            )

    async def _set_terminal(
        self,
        run_id: UUID,
        status: str,
        result: dict[str, Any],
        *,
        error: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id)
            if run is None:
                return
            run.status = status
            run.error = error
            if status in {"completed", "failed"}:
                run.current_node = None
            run.result_payload = self._json_safe(
                {
                    "decision": result.get("decision"),
                    "execution": result.get("execution"),
                    "performance": result.get("performance"),
                    "evidence": result.get("evidence", []),
                }
            )
            event = await repository.add_event(
                run_id,
                f"run_{status}",
                payload={"error": error} if error else {},
            )
            await session.commit()
        await self._publish(run, event.event_type, event.payload)

    async def _enter_node(self, state: AgentState, node: str) -> bool:
        run_id = UUID(state["run_id"])
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id)
            if run is None:
                raise LookupError("Agent run disappeared during execution.")
            if run.cancel_requested or run.status == "cancelled":
                run.status = "cancelled"
                event = await repository.add_event(
                    run_id,
                    "run_cancelled",
                    node=node,
                    payload={"reason": "Cancellation observed at workflow checkpoint."},
                )
                await session.commit()
                await self._publish(run, event.event_type, event.payload)
                return True
            if run.status == "paused":
                event = await repository.add_event(
                    run_id,
                    "checkpoint_paused",
                    node=node,
                    payload={"checkpoint": "before_node"},
                )
                await session.commit()
                await self._publish(run, event.event_type, event.payload)
                interrupt({"run_id": str(run_id), "node": node, "paused": True})
            run.status = "running"
            run.current_node = node
            event = await repository.add_event(
                run_id,
                "node_started",
                node=node,
                payload={"checkpoint": "node_start"},
            )
            await session.commit()
        await self._publish(run, event.event_type, event.payload)
        return False

    async def _finish_node(
        self,
        state: AgentState,
        node: str,
        status: str,
        latency_ms: int,
        *,
        failure: str | None = None,
    ) -> None:
        run_id = UUID(state["run_id"])
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            run = await repository.get_run(run_id)
            if run is None:
                raise LookupError("Agent run disappeared during node completion.")
            await repository.add_telemetry(
                run_id,
                node,
                status,
                latency_ms=latency_ms,
                retries=0,
                failure_details=failure,
            )
            event = await repository.add_event(
                run_id,
                "node_failed" if failure else "node_completed",
                agent=node if node in AGENT_NAMES else None,
                node=node,
                payload={"latency_ms": latency_ms, "error_type": failure},
            )
            await session.commit()
        await self._publish(run, event.event_type, event.payload)

    async def _emit_agent_result(
        self,
        state: AgentState,
        agent: str,
        result: AnalystOutput,
        *,
        strategy_version_id: UUID | None = None,
    ) -> None:
        run_id = UUID(state["run_id"])
        evidence = [
            item for item in state.get("evidence", []) if item.get("id") in result.evidence_ids
        ]
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            await repository.add_decision(
                run_id,
                state["symbol"],
                result.direction,
                result.status,
                result.rationale,
                evidence,
                agent=agent,
                confidence=result.confidence,
                strategy_version_id=strategy_version_id,
            )
            await repository.add_communication(
                run_id,
                agent,
                "strategy",
                result.model_dump(mode="json"),
            )
            await session.commit()

    async def _market_data(self, state: AgentState) -> dict[str, Any]:
        candles, provider = await self._market_router.get_candles(
            state["symbol"],
            state["interval"],
            500,
        )
        if not candles:
            raise ProviderUnavailable("Market data", "No candles were returned for analysis.")
        if not candle_is_fresh(
            candles[-1],
            INTERVAL_SECONDS[state["interval"]],
        ):
            raise ProviderUnavailable(
                "Market data",
                "The latest validated candle is stale; agent analysis was stopped.",
            )
        values = {
            "times": [item.time for item in candles],
            "opens": [item.open for item in candles],
            "highs": [item.high for item in candles],
            "lows": [item.low for item in candles],
            "closes": [item.close for item in candles],
            "volumes": [item.volume for item in candles],
        }
        indicator_series = calculate_indicators(
            **values,
            parameters=IndicatorParameters(),
        )
        last_time = candles[-1].time
        close = candles[-1].close
        ema = {
            period: series[-1] if series else None
            for period, series in indicator_series.ema.items()
        }
        latest = {
            "close": close,
            "ema": ema,
            "rsi": indicator_series.rsi[-1],
            "macd": indicator_series.macd[-1],
            "macd_signal": indicator_series.macd_signal[-1],
            "adx": indicator_series.adx[-1],
        }
        candle_id = f"candle:{state['symbol']}:{last_time.isoformat()}"
        indicator_id = f"indicators:{state['symbol']}:{last_time.isoformat()}"
        evidence = [
            Evidence(
                id=candle_id,
                source=provider,
                observed_at=last_time,
                content=(
                    f"{state['symbol']} {state['interval']} OHLCV candle: "
                    f"open={candles[-1].open}, high={candles[-1].high}, "
                    f"low={candles[-1].low}, close={close}, volume={candles[-1].volume}."
                ),
            ).model_dump(mode="json"),
            Evidence(
                id=indicator_id,
                source=provider,
                observed_at=last_time,
                content="Deterministic indicators derived from the validated candle series: "
                + json.dumps(latest, sort_keys=True),
            ).model_dump(mode="json"),
        ]
        return {
            "candles": [item.model_dump(mode="json") for item in candles],
            "provider": provider,
            "technical_snapshot": {
                **latest,
                "observed_at": last_time.isoformat(),
                "source": provider,
            },
            "evidence": evidence,
            "evidence_sources": {candle_id: provider, indicator_id: provider},
        }

    async def _fundamental(self, state: AgentState) -> dict[str, Any]:
        contract = FundamentalAgentInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
        )
        result = FundamentalAgentOutput(
            status="unavailable",
            direction="abstain",
            rationale=f"No verified fundamental-data provider is connected for {contract.symbol}.",
            diagnostics="Fundamental evidence source is not configured.",
            generated_at=datetime.now(UTC),
        )
        await self._emit_agent_result(state, "fundamental", result)
        return {
            "assessments": {
                **state.get("assessments", {}),
                "fundamental": result.model_dump(mode="json"),
            }
        }

    async def _sentiment(self, state: AgentState) -> dict[str, Any]:
        contract = SentimentAgentInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
        )
        result = SentimentAgentOutput(
            status="unavailable",
            direction="abstain",
            rationale=f"No verified sentiment/news source is connected for {contract.symbol}.",
            diagnostics="A market sentiment provider is required for this agent.",
            generated_at=datetime.now(UTC),
        )
        await self._emit_agent_result(state, "sentiment", result)
        return {
            "assessments": {
                **state.get("assessments", {}),
                "sentiment": result.model_dump(mode="json"),
            }
        }

    async def _technical(self, state: AgentState) -> dict[str, Any]:
        contract = TechnicalAgentInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            snapshot=TechnicalSnapshot.model_validate(state["technical_snapshot"]),
        )
        snapshot = contract.snapshot
        ema20 = snapshot.ema.get(20)
        ema50 = snapshot.ema.get(50)
        if (
            ema20 is None
            or ema50 is None
            or snapshot.rsi is None
            or snapshot.macd is None
            or snapshot.macd_signal is None
        ):
            direction = "abstain"
            status = "abstained"
            rationale = "Not enough validated candles to calculate the required indicators."
        elif ema20 > ema50 and snapshot.rsi >= 50 and snapshot.macd > snapshot.macd_signal:
            direction = "bullish"
            status = "completed"
            rationale = "EMA20 is above EMA50, RSI is at least 50, and MACD is above its signal."
        elif ema20 < ema50 and snapshot.rsi <= 50 and snapshot.macd < snapshot.macd_signal:
            direction = "bearish"
            status = "completed"
            rationale = "EMA20 is below EMA50, RSI is at most 50, and MACD is below its signal."
        else:
            direction = "neutral"
            status = "completed"
            rationale = (
                "The deterministic EMA, RSI, and MACD conditions do not align directionally."
            )
        diagnostics = (
            "OpenAI provider is not configured; the deterministic indicator result is retained."
            if self._research_provider is None
            else None
        )
        evidence_ids = [item["id"] for item in state.get("evidence", [])]
        llm_telemetry: dict[str, Any] | None = None
        if self._research_provider is not None:
            started = time.perf_counter()
            try:
                execution = await self._research_chain.ainvoke(
                    {
                        "question": (
                            "Interpret only the supplied deterministic technical indicator "
                            "evidence. Return an evidence-backed direction or abstain."
                        ),
                        "evidence": [
                            ResearchEvidence.model_validate(item)
                            for item in state.get("evidence", [])
                        ],
                    }
                )
                research = ResearchExecution.model_validate(execution)
                llm_telemetry = {
                    "status": "completed",
                    "model": research.model,
                    "latency_ms": research.latency_ms,
                    "input_tokens": research.input_tokens,
                    "output_tokens": research.output_tokens,
                    "api_cost": research.api_cost,
                    "retries": research.retries,
                }
                if research.result.direction != "abstain" and research.result.evidence:
                    direction = research.result.direction
                    status = "completed"
                    rationale = research.result.summary
                    diagnostics = research.result.uncertainty
                    evidence_ids = [item.id for item in research.result.evidence]
                else:
                    direction = "abstain"
                    status = "abstained"
                    rationale = research.result.summary
                    diagnostics = research.result.uncertainty
            except ProviderUnavailable as error:
                llm_telemetry = {
                    "status": "failed",
                    "model": self._settings.openai_model,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "input_tokens": None,
                    "output_tokens": None,
                    "api_cost": None,
                    "retries": 0,
                    "failure_details": type(error).__name__,
                }
                diagnostics = (
                    "OpenAI analysis failed; the deterministic indicator result is retained."
                )
        result = TechnicalAgentOutput(
            status=status,
            direction=direction,
            rationale=rationale,
            diagnostics=diagnostics,
            evidence_ids=evidence_ids,
            generated_at=datetime.now(UTC),
        )
        await self._emit_agent_result(state, "technical", result)
        output = {
            "assessments": {
                **state.get("assessments", {}),
                "technical": result.model_dump(mode="json"),
            }
        }
        if llm_telemetry is not None:
            output["_llm_telemetry"] = llm_telemetry
        return output

    async def _invoke_research(self, payload: dict[str, Any]) -> ResearchExecution:
        if self._research_provider is None:
            raise ProviderUnavailable("OpenAI", "OpenAI research is not configured.")
        return await self._research_provider.analyze_with_telemetry(
            payload["question"],
            payload["evidence"],
        )

    async def _save_llm_telemetry(
        self,
        state: AgentState,
        agent: str,
        telemetry: dict[str, Any],
    ) -> None:
        async with self._session_factory() as session:
            await AgentRepository(session).add_telemetry(
                UUID(state["run_id"]),
                agent,
                telemetry["status"],
                model=telemetry.get("model"),
                latency_ms=telemetry.get("latency_ms"),
                input_tokens=telemetry.get("input_tokens"),
                output_tokens=telemetry.get("output_tokens"),
                api_cost=telemetry.get("api_cost"),
                retries=telemetry.get("retries", 0),
                failure_details=telemetry.get("failure_details"),
            )
            await session.commit()

    async def _strategy(self, state: AgentState) -> dict[str, Any]:
        assessments = {
            name: AnalystOutput.model_validate(value)
            for name, value in state.get("assessments", {}).items()
        }
        async with self._session_factory() as session:
            strategy_version = await AgentRepository(session).get_approved_strategy(
                state["owner_id"]
            )
        contract = StrategyAgentInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            assessments=list(assessments.values()),
            strategy_version=(
                StrategyVersion(
                    id=strategy_version.id,
                    name=strategy_version.name,
                    version=strategy_version.version,
                    parameters=strategy_version.parameters,
                    approved=strategy_version.status == "approved",
                )
                if strategy_version
                else None
            ),
        )
        candidate, quorum, _, _, _, _ = choose_candidate(
            {name: output for name, output in assessments.items()},
            state.get("evidence_sources", {}),
        )
        if contract.strategy_version is None:
            result = StrategyAgentOutput(
                status="unavailable",
                direction="abstain",
                proposed_side="none",
                rationale="No user-approved strategy version is available.",
                diagnostics="Strategy evaluation requires an approved persisted version.",
                generated_at=datetime.now(UTC),
            )
            version_payload = None
        elif not quorum or candidate == "abstain":
            result = StrategyAgentOutput(
                status="abstained",
                direction="abstain",
                proposed_side="none",
                rationale="The analyst evidence did not satisfy independent-source quorum.",
                generated_at=datetime.now(UTC),
            )
            version_payload = strategy_version
        else:
            side = (
                "long"
                if candidate == "bullish"
                else "short"
                if candidate == "bearish"
                else "none"
            )
            result = StrategyAgentOutput(
                status="completed" if side != "none" else "abstained",
                direction=candidate,
                proposed_side=side,
                rationale=(
                    f"Approved strategy {contract.strategy_version.name} "
                    f"v{contract.strategy_version.version} "
                    "accepted the evidence-quorum candidate."
                ),
                evidence_ids=[
                    evidence_id
                    for assessment in assessments.values()
                    for evidence_id in assessment.evidence_ids
                ],
                generated_at=datetime.now(UTC),
            )
            version_payload = strategy_version
        version_id = version_payload.id if version_payload is not None else None
        await self._emit_agent_result(
            state,
            "strategy",
            result,
            strategy_version_id=version_id,
        )
        serialized_version = (
            {
                "id": str(version_payload.id),
                "name": version_payload.name,
                "version": version_payload.version,
                "parameters": version_payload.parameters,
                "approved": version_payload.status == "approved",
            }
            if version_payload is not None
            else None
        )
        return {
            "strategy": result.model_dump(mode="json"),
            "strategy_version": serialized_version,
        }

    async def _risk_manager(self, state: AgentState) -> dict[str, Any]:
        strategy = StrategyAgentOutput.model_validate(state["strategy"])
        context = RiskContext(account_connected=False)
        contract = RiskManagerInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
            context=context,
            proposed_side=strategy.proposed_side,
        )
        risk = deterministic_risk_check(contract.context, contract.proposed_side)
        assessments = {
            name: AnalystOutput.model_validate(value)
            for name, value in state.get("assessments", {}).items()
        }
        decision = resolve_debate(
            assessments,
            state.get("evidence_sources", {}),
            strategy.direction,
            risk,
        )
        evidence_by_id = {item["id"]: item for item in state.get("evidence", [])}
        decision_evidence = [
            evidence_by_id[item["id"]]
            for item in state.get("evidence", [])
            if item["id"] in evidence_by_id
        ]
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            await repository.add_decision(
                UUID(state["run_id"]),
                state["symbol"],
                decision.direction,
                "vetoed" if not risk.allowed else "completed",
                "; ".join(risk.veto_reasons) if risk.veto_reasons else "Risk checks passed.",
                state.get("evidence", []),
                agent="risk_manager",
            )
            stored = await repository.add_decision(
                UUID(state["run_id"]),
                state["symbol"],
                decision.direction,
                decision.status,
                decision.rationale,
                decision_evidence,
                agent="consensus",
                strategy_version_id=(
                    UUID(state["strategy_version"]["id"])
                    if state.get("strategy_version")
                    else None
                ),
            )
            decision_id = stored.id
            await repository.add_communication(
                UUID(state["run_id"]),
                "risk_manager",
                "execution",
                risk.model_dump(mode="json"),
            )
            await session.commit()
        return {
            "risk": risk.model_dump(mode="json"),
            "risk_context": context.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "decision_id": str(decision_id),
        }

    async def _execution(self, state: AgentState) -> dict[str, Any]:
        decision = DebateDecision.model_validate(state["decision"])
        risk = RiskManagerOutput.model_validate(state["risk"])
        strategy = StrategyAgentOutput.model_validate(state["strategy"])
        contract = ExecutionAgentInput(
            run_id=UUID(state["run_id"]),
            symbol=state["symbol"],
            evidence=[Evidence.model_validate(item) for item in state.get("evidence", [])],
            decision=decision,
            strategy_version=(
                StrategyVersion.model_validate(state["strategy_version"])
                if state.get("strategy_version")
                else None
            ),
        )
        if contract.decision.status != "consensus" or not risk.allowed:
            result = ExecutionAgentOutput(
                status="rejected",
                engine="nextrade_paper_trading",
                reason="No consensus approved by the deterministic Risk Manager.",
            )
        else:
            context = RiskContext.model_validate(state["risk_context"])
            if context.proposed_notional is None:
                result = ExecutionAgentOutput(
                    status="rejected",
                    engine="nextrade_paper_trading",
                    reason="Risk-approved order notional is unavailable.",
                )
            else:
                result = await self._paper_engine.submit_order(
                    PaperOrderRequest(
                        decision_id=UUID(state["decision_id"]),
                        symbol=state["symbol"],
                        side=strategy.proposed_side,
                        notional=context.proposed_notional,
                        strategy_version_id=(
                            UUID(state["strategy_version"]["id"])
                            if state.get("strategy_version")
                            else None
                        ),
                    )
                )
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            await repository.add_decision(
                UUID(state["run_id"]),
                state["symbol"],
                decision.direction,
                result.status,
                result.reason or f"Paper engine status: {result.status}.",
                state.get("evidence", []),
                agent="execution",
                strategy_version_id=(
                    UUID(state["strategy_version"]["id"])
                    if state.get("strategy_version")
                    else None
                ),
            )
            await repository.add_communication(
                UUID(state["run_id"]),
                "execution",
                "paper_trading_engine",
                result.model_dump(mode="json"),
            )
            await repository.add_paper_execution(
                UUID(state["run_id"]),
                UUID(state["decision_id"]),
                result.status,
                result.model_dump(mode="json"),
                paper_order_id=result.paper_order_id,
                executed_at=result.executed_at,
            )
            await session.commit()
        return {"execution": result.model_dump(mode="json")}

    async def _performance_critic(self, state: AgentState) -> dict[str, Any]:
        owner_id = state["owner_id"]
        evaluations: dict[str, dict[str, Any]] = {}
        async with self._session_factory() as session:
            repository = AgentRepository(session)
            for agent in ("fundamental", "sentiment", "technical", "strategy"):
                rows = await repository.get_verified_observations(agent, owner_id)
                observations = [
                    EvaluationObservation(
                        verified=bool(row["verified"]),
                        direction=str(row["direction"]),
                        direction_correct=bool(row["direction_correct"]),
                        confidence=row["confidence"],
                        rule_adherent=row["rule_adherent"],
                        condition_key=row["condition_key"],
                    )
                    for row in rows
                ]
                critic_input = PerformanceCriticInput(
                    run_id=UUID(state["run_id"]),
                    symbol=state["symbol"],
                    verified_outcomes=[
                        VerifiedOutcome.model_validate(row) for row in rows
                    ],
                    historical_assessments=[
                        AnalystOutput.model_validate(value)
                        for value in state.get("assessments", {}).values()
                    ],
                )
                if any(not outcome.verified for outcome in critic_input.verified_outcomes):
                    raise ValueError("Unverified outcomes cannot enter performance evaluation.")
                metrics = evaluate_performance(observations)
                evaluations[agent] = metrics.model_dump(mode="json")
                await repository.add_evaluation(
                    owner_id,
                    agent,
                    metrics.model_dump(mode="json"),
                    metrics.methodology_version,
                )
            await repository.add_decision(
                UUID(state["run_id"]),
                state["symbol"],
                "abstain",
                "insufficient_verified_data",
                "No verified historical outcomes are available for the Performance Critic.",
                [],
                agent="performance_critic",
            )
            await session.commit()
        critic_metrics = evaluate_performance([])
        result = PerformanceCriticOutput(
            status="insufficient_verified_data",
            metrics=critic_metrics,
            evaluated_at=datetime.now(UTC),
        )
        return {
            "evaluations": evaluations,
            "performance": result.model_dump(mode="json"),
        }

    def _wrap_node(self, name: str, operation: NodeOperation) -> NodeOperation:
        async def run(state: AgentState) -> dict[str, Any]:
            if await self._enter_node(state, name):
                return {"cancelled": True}
            started = time.perf_counter()
            try:
                result = await operation(state)
            except GraphInterrupt:
                raise
            except Exception as error:
                await self._finish_node(
                    state,
                    name,
                    "failed",
                    int((time.perf_counter() - started) * 1000),
                    failure=type(error).__name__,
                )
                raise
            telemetry = result.pop("_llm_telemetry", None)
            if telemetry is not None:
                await self._save_llm_telemetry(state, name, telemetry)
            await self._finish_node(
                state,
                name,
                "completed",
                int((time.perf_counter() - started) * 1000),
            )
            return result

        return run

    async def _publish(self, run: Any, event_type: str, payload: dict[str, Any]) -> None:
        await self._event_hub.publish(
            run.owner_id,
            {
                "type": event_type,
                "run_id": str(run.id),
                "status": run.status,
                "node": run.current_node,
                "payload": self._json_safe(payload),
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {key: AgentOrchestrator._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [AgentOrchestrator._json_safe(item) for item in value]
        if isinstance(value, UUID):
            return str(value)
        return value
