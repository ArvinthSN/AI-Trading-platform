from abc import ABC, abstractmethod
from typing import Any

from app.domains.market.schemas.market import Candle, Instrument, Ticker


class MarketProvider(ABC):
    name: str

    @abstractmethod
    async def get_instruments(self) -> list[Instrument]:
        raise NotImplementedError

    @abstractmethod
    async def get_tickers(self) -> list[Ticker]:
        raise NotImplementedError

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[Candle]:
        raise NotImplementedError

    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 25) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError
