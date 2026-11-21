import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.core.research import OpenAIResearchProvider, ResearchEvidence
from app.domains.agents.services.events import AgentEventHub
from app.domains.agents.services.orchestrator import AgentOrchestrator
from app.domains.agents.services.paper_execution import HttpPaperTradingEngine, PaperOrderRequest
from app.domains.market.schemas.market import Candle


class CheckpointState(TypedDict, total=False):
    value: int


@pytest.mark.asyncio
async def test_langgraph_pause_resume_restores_checkpointed_node_state() -> None:
    checkpointer = InMemorySaver()

    async def node(state: CheckpointState) -> dict[str, int]:
        interrupt({"reason": "paused at checkpoint"})
        return {"value": state.get("value", 0) + 1}

    builder = StateGraph(CheckpointState)
    builder.add_node("step", node)
    builder.set_entry_point("step")
    builder.add_edge("step", END)
    graph = builder.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "pause-resume-test"}}

    paused = await graph.ainvoke({"value": 4}, config=config)
    resumed = await graph.ainvoke(Command(resume=True), config=config)

    assert paused["__interrupt__"]
    assert resumed["value"] == 5


@pytest.mark.asyncio
async def test_paper_engine_is_the_only_order_adapter() -> None:
    requests: list[httpx.Request] = []

    async def transport(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"paper_order_id": "paper-123"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        unconfigured = HttpPaperTradingEngine(client, Settings())
        unavailable = await unconfigured.submit_order(
            PaperOrderRequest(
                decision_id=uuid4(),
                symbol="BTCUSDT",
                side="long",
                notional=10,
            )
        )
        configured = HttpPaperTradingEngine(
            client,
            Settings(paper_trading_engine_url="https://paper.example"),
        )
        accepted = await configured.submit_order(
            PaperOrderRequest(
                decision_id=uuid4(),
                symbol="BTCUSDT",
                side="long",
                notional=10,
            )
        )

    assert unavailable.status == "unavailable"
    assert accepted.status == "accepted"
    assert accepted.paper_order_id == "paper-123"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.host == "paper.example"
    assert requests[0].url.path == "/api/v1/paper/orders"
    assert json.loads(requests[0].content)["mode"] == "paper"


@pytest.mark.asyncio
async def test_openai_provider_tracks_usage_and_rejects_unreferenced_evidence() -> None:
    evidence = ResearchEvidence(
        id="market-1",
        source="Test exchange fixture",
        observed_at=datetime.now(UTC),
        content="Controlled test fixture; not production data.",
    )
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "direction": "bullish",
                            "summary": "Test-only evidence summary.",
                            "uncertainty": "Test fixture.",
                            "evidence_ids": ["market-1"],
                        }
                    )
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8),
    )
    provider = object.__new__(OpenAIResearchProvider)
    provider._model = "test-model"
    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=response)))
    )

    execution = await provider.analyze_with_telemetry("test", [evidence])

    assert execution.input_tokens == 20
    assert execution.output_tokens == 8
    assert execution.api_cost is None
    assert execution.result.evidence[0].id == "market-1"

    response.choices[0].message.content = json.dumps(
        {
            "direction": "bullish",
            "summary": "Unsupported response.",
            "uncertainty": "None.",
            "evidence_ids": ["not-provided"],
        }
    )
    with pytest.raises(ProviderUnavailable, match="invalid evidence response"):
        await provider.analyze_with_telemetry("test", [evidence])


@pytest.mark.asyncio
async def test_market_provider_failure_is_not_converted_to_a_successful_analysis() -> None:
    orchestrator = object.__new__(AgentOrchestrator)

    class FailedMarketRouter:
        async def get_candles(self, *_args, **_kwargs):
            raise ProviderUnavailable("test market", "provider failed")

    orchestrator._market_router = FailedMarketRouter()
    with pytest.raises(ProviderUnavailable):
        await orchestrator._market_data(
            {
                "run_id": str(uuid4()),
                "owner_id": "test-user",
                "symbol": "BTCUSDT",
                "interval": "1h",
            }
        )


@pytest.mark.asyncio
async def test_market_data_adapter_supplies_timestamped_indicator_evidence() -> None:
    candle = Candle(
        time=datetime.now(UTC),
        open=100,
        high=102,
        low=99,
        close=101,
        volume=50,
        is_closed=True,
    )
    orchestrator = object.__new__(AgentOrchestrator)

    class MarketRouter:
        async def get_candles(self, symbol: str, interval: str, limit: int):
            assert (symbol, interval, limit) == ("BTCUSDT", "1m", 500)
            return [candle], "verified test provider"

    orchestrator._market_router = MarketRouter()
    result = await orchestrator._market_data(
        {
            "run_id": str(uuid4()),
            "owner_id": "test-user",
            "symbol": "BTCUSDT",
            "interval": "1m",
        }
    )

    assert result["provider"] == "verified test provider"
    assert result["technical_snapshot"]["close"] == 101
    assert result["technical_snapshot"]["observed_at"] == candle.time.isoformat()
    assert all(
        item["source"] == "verified test provider"
        for item in result["evidence"]
    )


@pytest.mark.asyncio
async def test_model_failure_preserves_deterministic_technical_assessment() -> None:
    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._research_provider = object()
    orchestrator._research_chain = SimpleNamespace(
        ainvoke=AsyncMock(side_effect=ProviderUnavailable("OpenAI", "model unavailable"))
    )
    orchestrator._settings = Settings(openai_model="test-model")
    orchestrator._emit_agent_result = AsyncMock()
    observed_at = datetime.now(UTC)
    state = {
        "run_id": str(uuid4()),
        "symbol": "BTCUSDT",
        "evidence": [
            {
                "id": "market-candle",
                "source": "verified test provider",
                "observed_at": observed_at.isoformat(),
                "content": "Controlled test fixture; not production data.",
            }
        ],
        "technical_snapshot": {
            "close": 101,
            "ema": {20: 100, 50: 99},
            "rsi": 60,
            "macd": 2,
            "macd_signal": 1,
            "adx": 20,
            "observed_at": observed_at.isoformat(),
            "source": "verified test provider",
        },
        "assessments": {},
    }

    result = await orchestrator._technical(state)

    assert result["assessments"]["technical"]["direction"] == "bullish"
    assert "deterministic indicator result is retained" in result["assessments"][
        "technical"
    ]["diagnostics"]
    assert result["_llm_telemetry"]["status"] == "failed"
    assert result["_llm_telemetry"]["retries"] == 0


@pytest.mark.asyncio
async def test_agent_event_hub_streams_only_to_subscribers_for_their_owner() -> None:
    hub = AgentEventHub()

    async with hub.subscribe("owner-a") as queue:
        await hub.publish("owner-a", {"event": "node-transition"})
        await hub.publish("owner-b", {"event": "unrelated"})

        assert await asyncio.wait_for(queue.get(), timeout=0.1) == {
            "event": "node-transition"
        }
        assert queue.empty()


@pytest.mark.asyncio
async def test_agent_recovery_requeues_running_runs_from_persisted_status() -> None:
    run = SimpleNamespace(id=uuid4(), status="running")

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return None

    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._session_factory = SessionContext
    orchestrator.start = AsyncMock()

    from unittest.mock import patch

    with patch(
        "app.domains.agents.services.orchestrator.AgentRepository.list_recoverable_runs",
        new=AsyncMock(return_value=[run]),
    ):
        await orchestrator.recover()

    orchestrator.start.assert_awaited_once_with(run.id, recover=True)
