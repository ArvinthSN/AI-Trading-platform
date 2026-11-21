from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    binance_api_base_url: str = "https://api.binance.com"
    binance_ws_base_url: str = "wss://stream.binance.com:9443"
    binance_request_timeout_seconds: float = 10
    coingecko_api_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None
    fear_greed_api_url: str = "https://api.alternative.me/fng/"
    trading_economics_api_key: str | None = None
    trading_economics_api_base_url: str = "https://api.tradingeconomics.com"
    news_rss_url: str | None = None
    regulatory_rss_url: str | None = None
    geopolitical_rss_url: str | None = None
    global_regions_api_url: str | None = None
    global_events_api_url: str | None = None
    geopolitical_events_api_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    paper_trading_engine_url: str | None = None
    paper_trading_engine_token: str | None = None
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    kraken_api_key: str | None = None
    kraken_api_secret: str | None = None
    kraken_rest_base_url: str = "https://api.kraken.com"
    kraken_ws_base_url: str = "wss://ws.kraken.com"
    coinbase_api_key: str | None = None
    coinbase_api_secret: str | None = None
    coinbase_rest_base_url: str = "https://api.exchange.coinbase.com"
    coinbase_ws_base_url: str = "wss://ws-feed.exchange.coinbase.com"
    market_primary_provider: str = "kraken"
    market_secondary_provider: str = "coinbase"
    market_global_provider: str = "coingecko"
    market_websocket_enabled: bool = True
    market_cache_enabled: bool = True
    coingecko_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
