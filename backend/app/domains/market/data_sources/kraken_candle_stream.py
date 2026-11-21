import json
import logging
import math
from datetime import UTC, datetime

from websockets.asyncio.client import connect

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.schemas.market import Candle

logger = logging.getLogger(__name__)

INTERVALS = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}


class KrakenCandleStream:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.kraken_ws_base_url.rstrip("/")

    async def stream(self, symbol: str, interval: str):
        pair = _kraken_pair(symbol)
        interval_minutes = INTERVALS.get(interval)
        if pair is None or interval_minutes is None:
            raise ValueError("Unsupported Kraken candle pair or interval.")
        subscription = {
            "event": "subscribe",
            "pair": [pair],
            "subscription": {"name": "ohlc", "interval": interval_minutes},
        }
        try:
            async with connect(
                self._url,
                open_timeout=10,
                close_timeout=3,
                ping_interval=20,
                ping_timeout=20,
            ) as socket:
                await socket.send(json.dumps(subscription))
                async for message in socket:
                    candle = _parse_ohlc(message)
                    if candle is not None:
                        yield candle
        except (OSError, TimeoutError) as error:
            logger.warning("kraken_ohlc_stream_failed error=%s", type(error).__name__)
            raise ProviderUnavailable("Kraken WebSocket", "Candle stream disconnected.") from error


def _kraken_pair(symbol: str) -> str | None:
    normalized = symbol.upper().replace("-", "").replace("/", "")
    if normalized in {"BTCUSD", "XBTUSD"}:
        return "XBT/USD"
    if normalized.endswith("USD"):
        return f"{normalized[:-3]}/USD"
    if normalized.endswith("USDT"):
        return f"{normalized[:-4]}/USDT"
    return None


def _parse_ohlc(message: str | bytes) -> Candle | None:
    try:
        payload = json.loads(message)
        if not isinstance(payload, list) or len(payload) < 5:
            return None
        data = payload[1]
        channel_name = payload[-2]
        if channel_name != "ohlc" or not isinstance(data, list) or len(data) < 8:
            return None
        candle = Candle(
            time=datetime.fromtimestamp(float(data[1]), tz=UTC),
            open=float(data[2]),
            high=float(data[3]),
            low=float(data[4]),
            close=float(data[5]),
            volume=float(data[6]),
            is_closed=bool(data[-1]),
        )
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if not all(math.isfinite(value) for value in values):
            return None
        if candle.volume < 0 or candle.low > candle.high:
            return None
        if (
            candle.high < max(candle.open, candle.close)
            or candle.low > min(candle.open, candle.close)
        ):
            return None
        return candle
    except (ValueError, TypeError, IndexError, OverflowError):
        return None
