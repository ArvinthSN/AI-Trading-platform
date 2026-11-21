from datetime import UTC, datetime

from app.domains.market.schemas.market import Candle


def candle_is_fresh(
    candle: Candle, interval_seconds: int, maximum_delay_seconds: int = 120
) -> bool:
    if not candle.is_closed:
        return True
    age = (datetime.now(UTC) - candle.time).total_seconds()
    return age <= interval_seconds + maximum_delay_seconds
