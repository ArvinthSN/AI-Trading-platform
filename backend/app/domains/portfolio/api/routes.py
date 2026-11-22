from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.auth import CurrentUser
from app.core.errors import ProviderUnavailable
from app.domains.portfolio.providers.binance import BinancePortfolioProvider
from app.domains.portfolio.providers.paper_engine import PaperPortfolioProvider
from app.domains.portfolio.schemas import (
    PortfolioCalendarDay,
    PortfolioHolding,
    PortfolioPoint,
    PortfolioSources,
    PortfolioSummary,
    PortfolioTrade,
)

router = APIRouter()
Source = Literal["paper", "binance"]
Range = Literal["7D", "30D", "90D", "1Y", "ALL"]


def _providers(request: Request):
    client = request.app.state.http_client
    settings = request.app.state.settings
    return (
        PaperPortfolioProvider(client, settings),
        BinancePortfolioProvider(client, settings),
    )


def _raise_unavailable(error: ProviderUnavailable) -> None:
    raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/sources", response_model=PortfolioSources)
async def portfolio_sources(request: Request, user: CurrentUser) -> dict:
    paper, binance = _providers(request)
    return {
        "mode": "read_only",
        "sources": [
            {"id": "paper", "label": "Paper Trading", "configured": paper.configured},
            {"id": "binance", "label": "Binance Spot", "configured": binance.configured},
        ],
    }


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
) -> dict:
    paper, binance = _providers(request)
    if source == "paper":
        try:
            result = await paper.get("summary", user.subject)
            if not isinstance(result, dict):
                raise ProviderUnavailable(
                    "Paper Trading Engine", "Paper summary response must be an object."
                )
            return result
        except ProviderUnavailable as error:
            _raise_unavailable(error)

    try:
        account = await binance.account()
        balances = [
            item
            for item in account["balances"]
            if float(item.get("free", 0)) + float(item.get("locked", 0)) > 0
        ]
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
            "reason": (
                "Account balances are authenticated; quote-currency valuation "
                "requires live conversion prices."
            ),
        }
    except ProviderUnavailable as error:
        _raise_unavailable(error)


@router.get("/performance", response_model=list[PortfolioPoint])
async def portfolio_performance(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    range: Range = Query(default="30D"),
) -> list[dict]:
    if source == "binance":
        raise HTTPException(
            status_code=503,
            detail=(
                "Historical account equity is not available from spot trade "
                "history alone."
            ),
        )
    paper, _ = _providers(request)
    try:
        result = await paper.get("performance", user.subject, {"range": range})
        if not isinstance(result, list):
            raise ProviderUnavailable(
                "Paper Trading Engine", "Paper performance response must be a list."
            )
        return result
    except ProviderUnavailable as error:
        _raise_unavailable(error)


@router.get("/holdings", response_model=list[PortfolioHolding])
async def portfolio_holdings(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
) -> list[dict]:
    paper, binance = _providers(request)
    try:
        if source == "paper":
            result = await paper.get("holdings", user.subject)
            if not isinstance(result, list):
                raise ProviderUnavailable(
                    "Paper Trading Engine", "Paper holdings response must be a list."
                )
            return result

        account = await binance.account()
        return [
            {
                "asset": item["asset"],
                "symbol": item["asset"],
                "quantity": float(item.get("free", 0))
                + float(item.get("locked", 0)),
                "average_entry_price": None,
                "current_price": None,
                "market_value": None,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "allocation_pct": None,
            }
            for item in account["balances"]
            if float(item.get("free", 0)) + float(item.get("locked", 0)) > 0
        ]
    except ProviderUnavailable as error:
        _raise_unavailable(error)


@router.get("/calendar", response_model=list[PortfolioCalendarDay])
async def portfolio_calendar(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    range: Range = Query(default="30D"),
) -> list[dict]:
    if source == "binance":
        raise HTTPException(
            status_code=503,
            detail="Daily equity P&L requires historical account valuations.",
        )
    paper, _ = _providers(request)
    try:
        result = await paper.get("calendar", user.subject, {"range": range})
        if not isinstance(result, list):
            raise ProviderUnavailable(
                "Paper Trading Engine", "Paper calendar response must be a list."
            )
        return result
    except ProviderUnavailable as error:
        _raise_unavailable(error)


@router.get("/trades", response_model=list[PortfolioTrade])
async def portfolio_trades(
    request: Request,
    user: CurrentUser,
    source: Source = "paper",
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
    symbol: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{5,30}$")] = None,
) -> list[dict]:
    paper, binance = _providers(request)
    try:
        if source == "paper":
            result = await paper.get("trades", user.subject, {"limit": str(limit)})
            if not isinstance(result, list):
                raise ProviderUnavailable(
                    "Paper Trading Engine", "Paper trades response must be a list."
                )
            return result

        if not symbol:
            raise HTTPException(
                status_code=422,
                detail="A Binance symbol is required to request account trade history.",
            )
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
        _raise_unavailable(error)


@router.get("/agent-consistency")
async def portfolio_agent_consistency(user: CurrentUser) -> list[dict]:
    del user
    raise HTTPException(
        status_code=503,
        detail=(
            "Portfolio-linked agent consistency is unavailable until verified "
            "agent outcomes are joined to portfolio executions."
        ),
    )
