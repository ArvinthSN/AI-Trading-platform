import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ProviderUnavailable
from app.domains.market.providers.base import MarketProvider
from app.domains.market.providers.binance import BinanceSpotProvider
from app.domains.market.providers.coinbase import CoinbaseExchangeProvider
from app.domains.market.providers.kraken import KrakenProvider
from app.domains.market.router.health import ProviderHealthState
from app.domains.market.schemas.market import Candle, Instrument, Ticker
from app.domains.market.schemas.providers import ProviderDiagnostic

logger = logging.getLogger(__name__)


class ProviderRouter:
    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self.settings = settings
        self.health = {
            "binance": ProviderHealthState(
                name="Binance Spot",
                routing_role="primary",
            ),
            "kraken": ProviderHealthState(
                name="Kraken",
                routing_role="primary",
            ),
            "coinbase": ProviderHealthState(
                name="Coinbase Exchange",
                routing_role="secondary",
            ),
            "coingecko": ProviderHealthState(
                name="CoinGecko",
                routing_role="global",
                websocket_state="unsupported",
            ),
        }
        self.providers: dict[str, MarketProvider] = {
            "binance": BinanceSpotProvider(
                client,
                settings,
                self.health["binance"],
            ),
            "kraken": KrakenProvider(client, settings, self.health["kraken"]),
            "coinbase": CoinbaseExchangeProvider(
                client,
                settings,
                self.health["coinbase"],
            ),
        }

    def ordered_providers(self) -> list[MarketProvider]:
        configured_primary = self.settings.market_primary_provider.lower()
        configured_secondary = self.settings.market_secondary_provider.lower()
        names = [configured_primary, configured_secondary]
        return [
            self.providers[name]
            for name in names
            if name in self.providers
        ]

    async def get_instruments(self) -> list[Instrument]:
        for provider in self.ordered_providers():
            try:
                return await provider.get_instruments()
            except ProviderUnavailable:
                logger.warning("provider_instruments_failed provider=%s", provider.name)
                continue
        raise ProviderUnavailable(
            "Market providers",
            "No connected exchange provides instrument data.",
        )

    async def get_tickers(self) -> list[Ticker]:
        for provider in self.ordered_providers():
            try:
                tickers = await provider.get_tickers()
                if tickers:
                    return tickers
            except ProviderUnavailable:
                logger.warning("provider_tickers_failed provider=%s", provider.name)
                continue
        raise ProviderUnavailable(
            "Market providers",
            "No connected exchange provides live ticker data.",
        )

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: int,
        provider_name: str | None = None,
    ) -> tuple[list[Candle], str]:
        providers = (
            [self.providers[provider_name]]
            if provider_name in self.providers
            else self.ordered_providers()
        )
        for provider in providers:
            try:
                candles = await provider.get_candles(symbol, interval, limit)
                if candles:
                    return candles, provider.name
            except (ProviderUnavailable, ValueError) as error:
                logger.warning(
                    "provider_candles_failed provider=%s error=%s",
                    provider.name,
                    type(error).__name__,
                )
                continue
        raise ProviderUnavailable(
            "Market providers",
            "No connected exchange provides validated historical candles.",
        )

    async def get_orderbook(
        self,
        symbol: str,
        depth: int,
        provider_name: str | None = None,
    ) -> dict[str, Any]:
        providers = (
            [self.providers[provider_name]]
            if provider_name in self.providers
            else self.ordered_providers()
        )
        for provider in providers:
            try:
                return await provider.get_orderbook(symbol, depth)
            except ProviderUnavailable:
                continue
        raise ProviderUnavailable(
            "Market providers",
            "No connected exchange provides the requested order book.",
        )

    async def get_trades(
        self,
        symbol: str,
        limit: int,
        provider_name: str | None = None,
    ) -> list[dict[str, Any]]:
        providers = (
            [self.providers[provider_name]]
            if provider_name in self.providers
            else self.ordered_providers()
        )
        for provider in providers:
            try:
                trades = await provider.get_trades(symbol, limit)
                if trades:
                    return trades
            except ProviderUnavailable:
                continue
        raise ProviderUnavailable(
            "Market providers",
            "No connected exchange provides validated trades.",
        )

    def health_snapshots(self) -> list[Any]:
        return [state.snapshot() for state in self.health.values()]

    def diagnostics(self) -> list[ProviderDiagnostic]:
        kraken_configured = bool(
            self.settings.kraken_api_key
            and self.settings.kraken_api_secret
        )
        coinbase_configured = bool(
            self.settings.coinbase_api_key
            and self.settings.coinbase_api_secret
        )
        coingecko_configured = bool(
            self.settings.coingecko_api_key
            and str(self.settings.coingecko_api_key).startswith("CG-")
        )
        return [
            ProviderDiagnostic(
                name="Binance Spot",
                active=True,
                capabilities=[
                    "tickers",
                    "candles",
                    "orderbook",
                    "trades",
                    "websocket",
                ],
                public_market_data=True,
                authentication_required_for_public_data=False,
                configuration_status="public",
            ),
            ProviderDiagnostic(
                name="Kraken",
                active=True,
                capabilities=["tickers", "candles", "orderbook", "trades", "websocket"],
                public_market_data=True,
                authentication_required_for_public_data=False,
                configuration_status="configured" if kraken_configured else "public",
            ),
            ProviderDiagnostic(
                name="Coinbase Exchange",
                active=True,
                capabilities=["tickers", "candles", "orderbook", "trades", "websocket"],
                public_market_data=True,
                authentication_required_for_public_data=False,
                configuration_status="configured" if coinbase_configured else "public",
            ),
            ProviderDiagnostic(
                name="CoinGecko",
                active=True,
                capabilities=["global", "rankings"],
                public_market_data=True,
                authentication_required_for_public_data=False,
                configuration_status="configured" if coingecko_configured else "public",
            ),
        ]
