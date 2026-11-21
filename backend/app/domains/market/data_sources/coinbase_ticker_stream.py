import json
import logging
from datetime import UTC, datetime

from websockets.asyncio.client import connect

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.schemas.market import Ticker

logger = logging.getLogger(__name__)


class CoinbaseTickerStream:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.coinbase_ws_base_url.rstrip("/")

    async def stream(self, symbol: str | None = None):
        product_id = _coinbase_product(symbol)
        subscribe: dict[str, object] = {
            "type": "subscribe",
            "channels": (
                [{"name": "ticker", "product_ids": [product_id]}]
                if product_id
                else [{"name": "ticker"}]
            ),
        }
        try:
            async with connect(
                self._url,
                open_timeout=10,
                close_timeout=3,
                ping_interval=20,
                ping_timeout=20,
            ) as socket:
                await socket.send(json.dumps(subscribe))
                async for message in socket:
                    ticker = _parse_ticker(message)
                    if ticker is not None:
                        yield ticker
        except (OSError, TimeoutError) as error:
            logger.warning("coinbase_websocket_io_error error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "Coinbase WebSocket",
                "Ticker stream disconnected.",
            ) from error


def _coinbase_product(symbol: str | None) -> str | None:
    if not symbol:
        return None
    normalized = symbol.upper().replace("/", "").replace("-", "")
    if normalized in {"BTCUSD", "XBTUSD"}:
        return "BTC-USD"
    if normalized.endswith("USD"):
        return f"{normalized[:-3]}-USD"
    if normalized.endswith("USDT"):
        return f"{normalized[:-4]}-USDT"
    return None


def _parse_ticker(message: str | bytes) -> Ticker | None:
    try:
        payload = json.loads(message)
        if not isinstance(payload, dict) or payload.get("type") != "ticker":
            return None
        product_id = str(payload["product_id"])
        price = float(payload["price"])
        volume = float(payload["volume_24h"])
        opening = float(payload.get("open_24h", 0) or 0)
        if price <= 0 or volume < 0:
            return None
        symbol = product_id.replace("-", "")
        return Ticker(
            symbol=symbol,
            price=price,
            change_24h=(price - opening) / opening * 100 if opening else 0.0,
            volume_24h=volume,
            updated_at=datetime.now(UTC),
            source="Coinbase Exchange",
        )
    except (ValueError, TypeError, KeyError):
        return None
