from typing import Literal
from datetime import datetime

from pydantic import BaseModel


PortfolioSource = Literal["paper", "binance"]


class PortfolioSourceItem(BaseModel):
    id: PortfolioSource
    label: str
    configured: bool


class PortfolioSources(BaseModel):
    mode: Literal["read_only"]
    sources: list[PortfolioSourceItem]


class PortfolioSummary(BaseModel):
    source: PortfolioSource
    currency: str = "USDT"
    invested_capital: float | None = None
    current_value: float | None = None
    asset_count: int | None = None
    valuation_status: Literal["available", "unavailable"] | None = None
    reason: str | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    total_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    as_of: datetime | None = None


class PortfolioPoint(BaseModel):
    timestamp: datetime
    value: float


class PortfolioHolding(BaseModel):
    asset: str
    symbol: str
    quantity: float
    average_entry_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    allocation_pct: float | None = None


class PortfolioCalendarDay(BaseModel):
    date: str
    realized_pnl: float
    unrealized_pnl: float
    trade_count: int


class PortfolioTrade(BaseModel):
    id: str
    executed_at: datetime
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    realized_pnl: float | None = None
    source: Literal["manual", "agent", "strategy"] = "manual"


class PortfolioUnavailable(BaseModel):
    source: PortfolioSource
    status: Literal["unavailable"] = "unavailable"
