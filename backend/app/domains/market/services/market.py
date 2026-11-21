from datetime import UTC, datetime

from app.domains.market.schemas.market import (
    BreadthCount,
    MarketBreadth,
    MarketMovers,
    Ticker,
    VolumeShare,
)

ELIGIBLE_UNIVERSE = (
    "All active Binance Spot instruments quoted in USDT, as reported by exchangeInfo."
)


def build_market_views(
    tickers: list[Ticker],
    eligible_symbols: set[str],
    now: datetime | None = None,
    limit: int = 10,
) -> tuple[MarketBreadth, MarketMovers]:
    refreshed_at = now or datetime.now(UTC)
    universe = [ticker for ticker in tickers if ticker.symbol in eligible_symbols]
    gainers = [ticker for ticker in universe if ticker.change_24h > 0]
    losers = [ticker for ticker in universe if ticker.change_24h < 0]
    unchanged = [ticker for ticker in universe if ticker.change_24h == 0]
    total = len(universe)
    total_volume = sum(ticker.volume_24h for ticker in universe)

    def count(items: list[Ticker]) -> BreadthCount:
        return BreadthCount(
            count=len(items), percent=None if total == 0 else len(items) / total * 100
        )

    top_volume = sorted(universe, key=lambda ticker: ticker.volume_24h, reverse=True)[:limit]
    breadth = MarketBreadth(
        source="Binance Spot",
        updated_at=refreshed_at,
        eligible_universe=ELIGIBLE_UNIVERSE,
        total_tracked=total,
        gainers=count(gainers),
        losers=count(losers),
        unchanged=count(unchanged),
        volume_distribution=[
            VolumeShare(
                symbol=ticker.symbol,
                quote_volume=ticker.volume_24h,
                share_percent=None if total_volume == 0 else ticker.volume_24h / total_volume * 100,
            )
            for ticker in top_volume
        ],
        market_strength=None if total == 0 else (len(gainers) - len(losers)) / total * 100,
    )
    movers = MarketMovers(
        source="Binance Spot",
        updated_at=refreshed_at,
        gainers=sorted(gainers, key=lambda ticker: ticker.change_24h, reverse=True)[:limit],
        losers=sorted(losers, key=lambda ticker: ticker.change_24h)[:limit],
        highest_volume=top_volume,
    )
    return breadth, movers
