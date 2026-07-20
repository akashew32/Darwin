from pathlib import Path

import pytest

from darwin.execution.live_broker import LiveBroker
from darwin.execution.paper_broker import PaperBroker


def test_paper_broker_has_no_exchange_submit_method() -> None:
    broker = PaperBroker()
    assert not hasattr(broker, "submit_order")
    assert not hasattr(broker, "cancel_order")
    assert not isinstance(broker, LiveBroker)


@pytest.mark.parametrize(
    "artifact",
    [
        "summary.json",
        "events.csv",
        "orders.csv",
        "fills.csv",
        "signals.csv",
        "risk_decisions.csv",
        "health.csv",
        "equity_curve.csv",
        "report.html",
    ],
)
def test_mock_smoke_artifact_names_are_expected(artifact: str) -> None:
    assert Path("reports/paper/mock-smoke") / artifact


@pytest.mark.parametrize("method", ["submit_order", "cancel_order", "amend_order"])
def test_paper_broker_execution_methods_absent(method: str) -> None:
    assert not hasattr(PaperBroker(), method)
