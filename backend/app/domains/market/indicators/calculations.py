import math
from collections.abc import Sequence


def _ema_contiguous(values: Sequence[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    seed_values: list[float] = []
    previous: float | None = None
    alpha = 2 / (period + 1)

    for index, value in enumerate(values):
        if value is None:
            seed_values = []
            previous = None
            continue
        if previous is None:
            seed_values.append(value)
            if len(seed_values) == period:
                previous = sum(seed_values) / period
                result[index] = previous
            continue
        previous = value * alpha + previous * (1 - alpha)
        result[index] = previous
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    return _ema_contiguous(values, period)


def sma(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1 : index + 1]
        result[index] = sum(window) / period
    return result


def _sma_contiguous(
    values: Sequence[float | None],
    period: int,
) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1 : index + 1]
        if all(value is not None for value in window):
            result[index] = sum(value for value in window if value is not None) / period
    return result


def rsi(values: Sequence[float], period: int) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, len(values))]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, len(values))]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def value_for(gain: float, loss: float) -> float:
        if loss == 0:
            return 50.0 if gain == 0 else 100.0
        return 100 - 100 / (1 + gain / loss)

    result[period] = value_for(average_gain, average_loss)
    for index in range(period + 1, len(values)):
        change_index = index - 1
        average_gain = (average_gain * (period - 1) + gains[change_index]) / period
        average_loss = (average_loss * (period - 1) + losses[change_index]) / period
        result[index] = value_for(average_gain, average_loss)
    return result


def true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> list[float | None]:
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must have equal lengths")
    ranges: list[float | None] = [None] * len(highs)
    for index in range(1, len(highs)):
        ranges[index] = max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
    return ranges


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    ranges = true_range(highs, lows, closes)
    result: list[float | None] = [None] * len(ranges)
    if len(ranges) <= period:
        return result
    initial = [value for value in ranges[1 : period + 1] if value is not None]
    if len(initial) != period:
        return result
    current = sum(initial) / period
    result[period] = current
    for index in range(period + 1, len(ranges)):
        current = (current * (period - 1) + (ranges[index] or 0)) / period
        result[index] = current
    return result


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float | None]:
    if period < 1:
        raise ValueError("period must be positive")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must have equal lengths")
    length = len(highs)
    result: list[float | None] = [None] * length
    if length <= period * 2:
        return result
    ranges = true_range(highs, lows, closes)
    positive_dm: list[float | None] = [None] * length
    negative_dm: list[float | None] = [None] * length
    for index in range(1, length):
        up_move = highs[index] - highs[index - 1]
        down_move = lows[index - 1] - lows[index]
        positive_dm[index] = up_move if up_move > down_move and up_move > 0 else 0.0
        negative_dm[index] = down_move if down_move > up_move and down_move > 0 else 0.0

    first_range = sum(value or 0 for value in ranges[1 : period + 1])
    first_positive = sum(value or 0 for value in positive_dm[1 : period + 1])
    first_negative = sum(value or 0 for value in negative_dm[1 : period + 1])
    smoothed_range = first_range
    smoothed_positive = first_positive
    smoothed_negative = first_negative
    dx_values: list[float | None] = [None] * length

    def calculate_dx(tr: float, plus: float, minus: float) -> float:
        if tr == 0:
            return 0.0
        plus_di = 100 * plus / tr
        minus_di = 100 * minus / tr
        denominator = plus_di + minus_di
        return 0.0 if denominator == 0 else 100 * abs(plus_di - minus_di) / denominator

    dx_values[period] = calculate_dx(smoothed_range, smoothed_positive, smoothed_negative)
    for index in range(period + 1, length):
        smoothed_range = smoothed_range - smoothed_range / period + (ranges[index] or 0)
        smoothed_positive = (
            smoothed_positive - smoothed_positive / period + (positive_dm[index] or 0)
        )
        smoothed_negative = (
            smoothed_negative - smoothed_negative / period + (negative_dm[index] or 0)
        )
        dx_values[index] = calculate_dx(smoothed_range, smoothed_positive, smoothed_negative)

    first_adx_index = period * 2 - 1
    initial_dx = [value for value in dx_values[period : first_adx_index + 1] if value is not None]
    if len(initial_dx) != period:
        return result
    current_adx = sum(initial_dx) / period
    result[first_adx_index] = current_adx
    for index in range(first_adx_index + 1, length):
        current_adx = (current_adx * (period - 1) + (dx_values[index] or 0)) / period
        result[index] = current_adx
    return result


def macd(
    values: Sequence[float],
    fast_period: int,
    slow_period: int,
    signal_period: int,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")
    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    line = [
        fast_value - slow_value if fast_value is not None and slow_value is not None else None
        for fast_value, slow_value in zip(fast, slow, strict=True)
    ]
    signal = _ema_contiguous(line, signal_period)
    histogram = [
        value - signal_value if value is not None and signal_value is not None else None
        for value, signal_value in zip(line, signal, strict=True)
    ]
    return line, signal, histogram


def stochastic(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
    smooth: int = 3,
) -> tuple[list[float | None], list[float | None]]:
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low, and close series must have equal lengths")
    raw: list[float | None] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        highest = max(highs[index - period + 1 : index + 1])
        lowest = min(lows[index - period + 1 : index + 1])
        raw[index] = (
            50.0 if highest == lowest else 100 * (closes[index] - lowest) / (highest - lowest)
        )
    k_values = _sma_contiguous(raw, smooth)
    d_values = _sma_contiguous(k_values, smooth)
    return k_values, d_values


def bollinger(
    values: Sequence[float],
    period: int,
    standard_deviations: float,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    middle = sma(values, period)
    upper: list[float | None] = [None] * len(values)
    lower: list[float | None] = [None] * len(values)
    for index, mean in enumerate(middle):
        if mean is None:
            continue
        window = values[index - period + 1 : index + 1]
        variance = sum((value - mean) ** 2 for value in window) / period
        width = standard_deviations * math.sqrt(variance)
        upper[index] = mean + width
        lower[index] = mean - width
    return upper, middle, lower
