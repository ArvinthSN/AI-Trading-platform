from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import get_database_session
from app.core.errors import ProviderUnavailable
from app.domains.portfolio.providers.binance import BinancePortfolioProvider
from app.domains.portfolio.providers.paper_engine import PaperPortfolioProvider

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_database_session)]
Source = Literal["paper", "binance"]


def _providers(request: Request):
    client = request.app.state.http_client
    settings = request.app.state.settings
    return (
        PaperPortfolioProvider(client, settings),
        BinancePortfolioProvider(client, settings),
    )


def _unavailable(source: Source, error: Exception):
    raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/sources")
async def portfolio_sources(
    request: Request,
    user: CurrentUser,
) -> dict:
    del user
    paper, binance = _providers(request)
    return {
        "sources": [
            {"id": "paper", "label": "Paper Trading", "configured": paper.configured},
            {"id": "binance", "label": "Binance Spot", "configured": binance.configured},
        ],
        "mode": "read_only",
    }


@router.get("/summary")
async def portfolio_summary(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
) -> dict:
    del user
    paper, binance = _providers(request)
    if source == "paper":
        try:
            return await paper.get("summary")
        except ProviderUnavailable as error:
            _unavailable(source, error)
    try:
        account = await binance.account()
        balances = [item for item in account["balances"] if float(item.get("free", 0)) + float(item.get("locked", 0)) > 0]
        return {
            "source": "binance",
            "currency": "USDT",
            "invested_capital": None,
            "current_value": None,
            "realized_pnl": None,
            "unrealized_pnl": None,
            "total_return_pct": None,
            "max_drawdown_pct": None,
            "as_of": datetime.now(UTC),
            "asset_count": len(balances),
            "valuation_status": "unavailable",
            "reason": "Account balances are authenticated; quote-currency valuation requires live conversion prices.",
        }
    except ProviderUnavailable as error:
        _unavailable(source, error)


@router.get("/performance")
async def portfolio_performance(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    range: str = Query(default="30D", pattern=r"^(7D|30D|90D|1Y|ALL)$"),
) -> list[dict]:
    del user
    paper, _ = _providers(request)
    try:
        result = await paper.get("performance", {"range": range}) if source == "paper" else None
        if source == "binance":
            raise ProviderUnavailable("Binance account", "Historical account equity is not available from spot trade history alone.")
        if not isinstance(result, list):
            raise ProviderUnavailable("Paper Trading Engine", "Paper performance response must be a list.")
        return result
    except ProviderUnavailable as error:
        _unavailable(source, error)


@router.get("/holdings")
async def portfolio_holdings(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
) -> list[dict]:
    del user
    paper, binance = _providers(request)
    try:
        if source == "paper":
            result = await paper.get("holdings")
            if not isinstance(result, list):
                raise ProviderUnavailable("Paper Trading Engine", "Paper holdings response must be a list.")
            return result
        account = await binance.account()
        balances = account["balances"]
        return [
            {
                "asset": item["asset"],
                "symbol": f'{item["asset"]}USDT',
                "quantity": float(item.get("free", 0)) + float(item.get("locked", 0)),
                "average_entry_price": None,
                "current_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "allocation_pct": None,
            }
            for item in balances
            if float(item.get("free", 0)) + float(item.get("locked", 0)) > 0
        ]
    except ProviderUnavailable as error:
        _unavailable(source, error)


@router.get("/calendar")
async def portfolio_calendar(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    range: str = Query(default="30D", pattern=r"^(7D|30D|90D|1Y|ALL)$"),
) -> list[dict]:
    del user
    paper, _ = _providers(request)
    try:
        if source == "binance":
            raise ProviderUnavailable("Binance account", "Daily equity P&L requires historical account valuations.")
        result = await paper.get("calendar", {"range": range})
        if not isinstance(result, list):
            raise ProviderUnavailable("Paper Trading Engine", "Paper calendar response must be a list.")
        return result
    except ProviderUnavailable as error:
        _unavailable(source, error)


@router.get("/trades")
async def portfolio_trades(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    limit: int = Query(default=12, ge=1, le=100),
    symbol: str | None = Query(default=None, pattern=r"^[A-Z0-9]{5,30}$"),
) -> list[dict]:
    del user
    paper, binance = _providers(request)
    try:
        if source == "paper":
            result = await paper.get("trades", {"limit": str(limit)})
            if not isinstance(result, list):
                raise ProviderUnavailable("Paper Trading Engine", "Paper trades response must be a list.")
            return result
        if not symbol:
            raise HTTPException(status_code=422, detail="A Binance symbol is required to request account trade history.")
        trades = await binance.trades(symbol, limit)
        return [
            {
                "id": str(item["id"]),
                "executed_at": datetime.fromtimestamp(item["time"] / 1000, UTC),
                "symbol": symbol,
                "side": "buy" if item.get("isBuyer") else "sell",
                "quantity": float(item["qty"]),
                "price": float(item["price"]),
                "realized_pnl": None,
                "source": "manual",
            }
            for item in trades
        ]
    except ProviderUnavailable as error:
        _unavailable(source, error)


@router.get("/agent-consistency")
async def portfolio_agent_consistency(
    user: CurrentUser,
    session: DbSession,
) -> list[dict]:
    # Agent outcome evaluation is exposed separately by the agent domain today.
    # Do not infer portfolio performance from unverified agent decisions.
    del user, session
    return []
