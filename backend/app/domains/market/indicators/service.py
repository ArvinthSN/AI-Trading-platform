from collections.abc import Sequence
from datetime import datetime

from app.domains.market.indicators.calculations import (
    adx,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
    stochastic,
)
from app.domains.market.schemas.market import IndicatorParameters, IndicatorSeries


def calculate_indicators(
    times: Sequence[datetime],
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    volumes: Sequence[float],
    parameters: IndicatorParameters,
) -> IndicatorSeries:
    if len({len(times), len(opens), len(highs), len(lows), len(closes), len(volumes)}) != 1:
        raise ValueError("candle input series must have equal lengths")
    ema_values = {period: ema(closes, period) for period in parameters.ema_periods}
    macd_line, macd_signal, macd_histogram = macd(
        closes,
        parameters.macd_fast,
        parameters.macd_slow,
        parameters.macd_signal,
    )
    stochastic_k, stochastic_d = stochastic(
        highs,
        lows,
        closes,
        parameters.stochastic_period,
        parameters.stochastic_smooth,
    )
    upper, middle, lower = bollinger(
        closes,
        parameters.bollinger_period,
        parameters.bollinger_stddev,
    )
    volume_changes: list[float | None] = [None] * len(volumes)
    for index in range(1, len(volumes)):
        previous_volume = volumes[index - 1]
        if previous_volume != 0:
            volume_changes[index] = (volumes[index] - previous_volume) / previous_volume * 100
    return IndicatorSeries(
        times=list(times),
        ema=ema_values,
        sma=sma(closes, parameters.sma_period),
        adx=adx(highs, lows, closes, parameters.adx_period),
        rsi=rsi(closes, parameters.rsi_period),
        macd=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        stochastic_k=stochastic_k,
        stochastic_d=stochastic_d,
        atr=atr(highs, lows, closes, parameters.atr_period),
        bollinger_upper=upper,
        bollinger_middle=middle,
        bollinger_lower=lower,
        volume_sma=sma(volumes, parameters.volume_sma_period),
        volume_change_percent=volume_changes,
    )
