import re
from typing import Any

RISK_PARAMETER_TOKENS = {
    "drawdown",
    "exposure",
    "leverage",
    "loss",
    "position",
    "risk",
    "stop",
    "limit",
}


def contains_risk_parameter(parameters: dict[str, Any]) -> bool:
    for key in parameters:
        snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
        normalized = re.sub(r"[^a-z0-9]+", "_", snake_case.lower())
        tokens = set(normalized.split("_"))
        if tokens & RISK_PARAMETER_TOKENS:
            return True
    return False


def is_approvable_validation(validation: dict[str, Any] | None) -> bool:
    return bool(
        validation
        and validation.get("out_of_sample_validated") is True
        and validation.get("overfit_detected") is False
        and validation.get("paper_only") is True
    )
