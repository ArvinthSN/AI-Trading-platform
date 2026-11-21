import pytest

from app.domains.market.indicators.calculations import (
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
)


def test_sma_known_values() -> None:
    assert sma([1.0, 2.0, 3.0, 4.0, 5.0], 3) == [
        None,
        None,
        2.0,
        3.0,
        4.0,
    ]


def test_ema_known_values() -> None:
    result = ema([1.0, 2.0, 3.0, 4.0, 5.0], 3)
    assert result[2] == pytest.approx(2.0)
    assert result[4] == pytest.approx(4.0)


def test_rsi_flat_market_is_not_nan() -> None:
    result = rsi([100.0] * 20, 14)
    assert result[14] == 50.0


def test_atr_validates_equal_lengths() -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        atr([10.0], [9.0], [], 14)


def test_macd_requires_ordered_periods() -> None:
    with pytest.raises(ValueError, match="less than"):
        macd([1.0, 2.0, 3.0], 26, 12, 9)


def test_bollinger_bands_enclose_flat_market() -> None:
    upper, middle, lower = bollinger([10.0] * 20, 20, 2.0)
    assert upper[-1] == 10.0
    assert middle[-1] == 10.0
    assert lower[-1] == 10.0
