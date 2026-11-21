import json
import logging
from datetime import UTC, datetime
from typing import Any

from websockets.asyncio.client import connect

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.schemas.market import Ticker

logger = logging.getLogger(__name__)


class KrakenTickerStream:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.kraken_ws_base_url.rstrip("/")

    async def stream(self, symbol: str | None = None):
        pair = _kraken_pair(symbol)
        subscription: dict[str, Any] = {
            "event": "subscribe",
            "subscription": {"name": "ticker"},
        }
        if pair:
            subscription["pair"] = [pair]
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
                    ticker = _parse_ticker(message)
                    if ticker is not None:
                        yield ticker
        except (OSError, TimeoutError) as error:
            logger.warning("kraken_websocket_io_error error=%s", type(error).__name__)
            raise ProviderUnavailable("Kraken WebSocket", "Ticker stream disconnected.") from error


def _kraken_pair(symbol: str | None) -> str | None:
    if not symbol:
        return None
    normalized = symbol.upper().replace("-", "").replace("/", "")
    if normalized in {"BTCUSD", "XBTUSD"}:
        return "XBT/USD"
    if normalized.endswith("USD"):
        return f"{normalized[:-3]}/USD"
    if normalized.endswith("USDT"):
        return f"{normalized[:-4]}/USDT"
    return None


def _parse_ticker(message: str | bytes) -> Ticker | None:
    try:
        payload = json.loads(message)
        if not isinstance(payload, list) or len(payload) < 4:
            return None
        channel_name = payload[-2]
        pair_name = payload[-1]
        data = payload[1]
        if channel_name != "ticker" or not isinstance(data, dict):
            return None
        price = float(data["c"][0])
        opening = float(data["o"])
        volume = float(data["v"][1])
        if price <= 0 or volume < 0:
            return None
        symbol = str(pair_name).replace("/", "").replace("XBT", "BTC")
        return Ticker(
            symbol=symbol,
            price=price,
            change_24h=(price - opening) / opening * 100 if opening else 0.0,
            volume_24h=volume,
            updated_at=datetime.now(UTC),
            source="Kraken",
        )
    except (ValueError, TypeError, KeyError, IndexError):
        return None
