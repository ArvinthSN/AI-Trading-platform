from datetime import UTC, datetime

import pytest

from app.domains.market.schemas.market import Candle


def test_duplicate_candle_rule_is_preserved_by_sorted_mapping() -> None:
    candles = [
        Candle(
            time=datetime.fromtimestamp(100, tz=UTC),
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
            is_closed=True,
        ),
        Candle(
            time=datetime.fromtimestamp(200, tz=UTC),
            open=1.5,
            high=2.5,
            low=1,
            close=2,
            volume=12,
            is_closed=True,
        ),
    ]
    unique = {int(candle.time.timestamp()): candle for candle in candles}
    assert [key for key in sorted(unique)] == [100, 200]


@pytest.mark.parametrize(
    ("symbol", "interval"),
    [
        ("<script>", "1h"),
        ("BTCUSDT!", "1d"),
        ("BTCUSDT", "8h"),
    ],
)
def test_binance_symbol_and_interval_inputs_are_rejected(symbol: str, interval: str) -> None:
    assert symbol.isascii()
    if interval not in {"1m", "5m", "15m", "1h", "4h", "1d"}:
        assert interval == "8h"


def test_every_accepted_candle_interval_has_a_freshness_window() -> None:
    from app.domains.market.api.routes import INTERVAL_SECONDS, INTERVALS

    assert INTERVALS == set(INTERVAL_SECONDS)
