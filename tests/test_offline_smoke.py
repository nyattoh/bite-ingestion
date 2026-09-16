from __future__ import annotations

import pytest

from bite_ingestion.interfaces import (
    MorphologyProfiler,
    Operator,
    OperatorSequencePolicy,
    TargetModel,
    TokenMeter,
)
from bite_ingestion.offline_stubs import FixedPolicy, NullTokenMeter, OfflineTargetModel


def test_offline_target_model_refuses_calls() -> None:
    model = OfflineTargetModel()
    assert isinstance(model, TargetModel)
    with pytest.raises(RuntimeError):
        model.complete("ping")


def test_token_meter_and_policy_interfaces() -> None:
    meter = NullTokenMeter()
    assert isinstance(meter, TokenMeter)
    meter.record({"kind": "scaffold", "tokens": 0})
    assert meter.totals()["T_total"] == "TBD"
    policy = FixedPolicy()
    assert isinstance(policy, OperatorSequencePolicy)
    assert list(policy.propose({})) == []


def test_protocol_symbols_importable() -> None:
    assert MorphologyProfiler is not None
    assert Operator is not None
