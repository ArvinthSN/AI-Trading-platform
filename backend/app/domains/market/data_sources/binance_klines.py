import json
import logging
import math
from datetime import UTC, datetime

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.data_sources.binance import INTERVALS, SYMBOL_PATTERN
from app.domains.market.schemas.market import Candle

logger = logging.getLogger(__name__)


class BinanceKlineStream:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.binance_ws_base_url.rstrip("/")

    async def stream(self, symbol: str, interval: str):
        normalized_symbol = symbol.upper()
        if not SYMBOL_PATTERN.fullmatch(normalized_symbol) or interval not in INTERVALS:
            raise ValueError("Invalid market symbol or candle interval.")
        url = f"{self._base_url}/ws/{normalized_symbol.lower()}@kline_{interval}"
        try:
            async with connect(
                url,
                open_timeout=10,
                close_timeout=3,
                ping_interval=20,
                ping_timeout=20,
                max_size=1_000_000,
            ) as socket:
                async for message in socket:
                    candle = _parse_kline(message)
                    if candle is not None:
                        yield candle
        except WebSocketException as error:
            logger.warning("binance_kline_stream_failed error=%s", type(error).__name__)
            raise ProviderUnavailable("Binance WebSocket", "Candle stream disconnected.") from error
        except OSError as error:
            logger.warning("binance_kline_stream_io_error error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Binance WebSocket", "Candle stream could not be reached."
            ) from error


def _parse_kline(message: str | bytes) -> Candle | None:
    try:
        payload = json.loads(message)
        kline = payload["k"]
        candle = Candle(
            time=datetime.fromtimestamp(int(kline["t"]) / 1000, tz=UTC),
            open=float(kline["o"]),
            high=float(kline["h"]),
            low=float(kline["l"]),
            close=float(kline["c"]),
            volume=float(kline["v"]),
            is_closed=bool(kline["x"]),
        )
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if not all(math.isfinite(value) for value in values):
            return None
        if (
            candle.volume < 0
            or candle.high < max(candle.open, candle.close)
            or candle.low > min(candle.open, candle.close)
            or candle.low > candle.high
        ):
            return None
        return candle
    except (ValueError, KeyError, TypeError, OverflowError):
        logger.warning("binance_kline_message_invalid")
        return None
