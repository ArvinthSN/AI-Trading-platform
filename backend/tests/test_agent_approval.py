from app.domains.agents.approval import contains_risk_parameter, is_approvable_validation


def test_tuning_approval_requires_all_validation_gates() -> None:
    assert is_approvable_validation(
        {
            "out_of_sample_validated": True,
            "overfit_detected": False,
            "paper_only": True,
        }
    )
    assert not is_approvable_validation(
        {
            "out_of_sample_validated": False,
            "overfit_detected": False,
            "paper_only": True,
        }
    )
    assert not is_approvable_validation(None)


def test_strategy_tuner_cannot_change_risk_limits() -> None:
    assert contains_risk_parameter({"max_drawdown": 0.1})
    assert contains_risk_parameter({"position-size": 100})
    assert contains_risk_parameter({"stopLossPercent": 2})
    assert not contains_risk_parameter({"ema_period": 20, "signal_threshold": 0.5})
