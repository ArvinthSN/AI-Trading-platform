from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.agents.schemas import ExecutionAgentOutput


class PaperOrderRequest(BaseModel):
    decision_id: UUID
    symbol: str
    side: str
    notional: float = Field(gt=0)
    strategy_version_id: UUID | None = None
    mode: str = "paper"


class PaperTradingEngine(Protocol):
    async def submit_order(self, order: PaperOrderRequest) -> ExecutionAgentOutput: ...


class HttpPaperTradingEngine:
    """The sole order adapter; it has no exchange or brokerage fallback."""

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._url = settings.paper_trading_engine_url
        self._token = settings.paper_trading_engine_token

    async def submit_order(self, order: PaperOrderRequest) -> ExecutionAgentOutput:
        if not self._url:
            return ExecutionAgentOutput(
                status="unavailable",
                engine="nextrade_paper_trading",
                reason="NEXTRADE Paper Trading Engine is not configured.",
            )
        try:
            response = await self._client.post(
                f"{self._url.rstrip('/')}/api/v1/paper/orders",
                json=order.model_dump(mode="json"),
                headers={"Authorization": f"Bearer {self._token}"} if self._token else {},
            )
            response.raise_for_status()
            payload = response.json()
            order_id = payload.get("paper_order_id")
            if not isinstance(order_id, str) or not order_id:
                raise ProviderUnavailable(
                    "NEXTRADE Paper Trading Engine",
                    "Paper engine returned no paper_order_id.",
                )
        except httpx.HTTPError as error:
            raise ProviderUnavailable(
                "NEXTRADE Paper Trading Engine",
                "Paper order submission failed.",
            ) from error
        return ExecutionAgentOutput(
            status="accepted",
            engine="nextrade_paper_trading",
            paper_order_id=order_id,
            executed_at=datetime.now(UTC),
        )
