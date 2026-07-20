from dataclasses import dataclass, field
from datetime import datetime

from darwin.domain.orderbook import OrderBookSnapshot


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    message: str
    market_id: str | None = None
    ts: datetime | None = None


@dataclass
class DataQualityReport:
    issues: list[DataQualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues

    def add(
        self, code: str, message: str, market_id: str | None = None, ts: datetime | None = None
    ) -> None:
        self.issues.append(DataQualityIssue(code, message, market_id, ts))


def check_snapshots(snapshots: list[OrderBookSnapshot]) -> DataQualityReport:
    report = DataQualityReport()
    last_seq: dict[str, int] = {}
    last_ts: dict[str, datetime] = {}
    for snap in snapshots:
        if (
            snap.best_bid is not None
            and snap.best_ask is not None
            and snap.best_bid >= snap.best_ask
        ):
            report.add(
                "crossed_book",
                "best bid is greater than or equal to best ask",
                snap.market_id,
                snap.received_ts,
            )
        if snap.sequence is not None:
            previous = last_seq.get(snap.market_id)
            if previous is not None and snap.sequence < previous:
                report.add(
                    "sequence_regression",
                    "sequence moved backwards",
                    snap.market_id,
                    snap.received_ts,
                )
            last_seq[snap.market_id] = snap.sequence
        previous_ts = last_ts.get(snap.market_id)
        if previous_ts is not None and snap.received_ts < previous_ts:
            report.add(
                "timestamp_regression",
                "received timestamp moved backwards",
                snap.market_id,
                snap.received_ts,
            )
        last_ts[snap.market_id] = snap.received_ts
    return report
