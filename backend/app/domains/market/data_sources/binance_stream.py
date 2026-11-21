import json
import logging
import math
from datetime import UTC, datetime
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.data_sources.binance import SYMBOL_PATTERN
from app.domains.market.schemas.market import Ticker

logger = logging.getLogger(__name__)


class BinanceTickerStream:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.binance_ws_base_url.rstrip("/")

    async def stream(self, symbol: str | None = None):
        if symbol is not None and not SYMBOL_PATTERN.fullmatch(symbol):
            raise ValueError("Invalid market symbol.")
        stream_name = "!ticker@arr" if symbol is None else f"{symbol.lower()}@ticker"
        url = f"{self._base_url}/ws/{stream_name}"
        try:
            async with connect(
                url,
                open_timeout=10,
                close_timeout=3,
                ping_interval=20,
                ping_timeout=20,
                max_size=2_000_000,
            ) as socket:
                async for message in socket:
                    for ticker in _parse_message(message, symbol):
                        yield ticker
        except WebSocketException as error:
            logger.warning("binance_websocket_failed error=%s", type(error).__name__)
            raise ProviderUnavailable("Binance WebSocket", "Market stream disconnected.") from error
        except OSError as error:
            logger.warning("binance_websocket_io_error error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Binance WebSocket", "Market stream could not be reached."
            ) from error


def _parse_message(message: str | bytes, selected_symbol: str | None):
    try:
        payload: Any = json.loads(message)
    except (ValueError, TypeError):
        logger.warning("binance_websocket_invalid_json")
        return
    records = payload if isinstance(payload, list) else [payload]
    for record in records:
        if not isinstance(record, dict):
            continue
        symbol = record.get("s")
        if not isinstance(symbol, str) or (
            selected_symbol is not None and symbol != selected_symbol
        ):
            continue
        try:
            values = (
                float(record["c"]),
                float(record["P"]),
                float(record["q"]),
            )
            if not all(math.isfinite(value) for value in values):
                continue
            event_time = datetime.fromtimestamp(int(record["E"]) / 1000, tz=UTC)
            yield Ticker(
                symbol=symbol,
                price=values[0],
                change_24h=values[1],
                volume_24h=values[2],
                updated_at=event_time,
                source="Binance WebSocket",
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            logger.warning("binance_websocket_invalid_ticker symbol=%s", symbol)
