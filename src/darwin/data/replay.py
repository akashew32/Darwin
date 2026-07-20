import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReplayEvent:
    event_type: str
    received_ts: datetime
    payload: dict[str, Any]


def write_replay(path: Path, events: Iterable[ReplayEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for event in events:
            handle.write(
                json.dumps(
                    {
                        "event_type": event.event_type,
                        "received_ts": event.received_ts.isoformat(),
                        "payload": event.payload,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def read_replay(path: Path) -> Iterator[ReplayEvent]:
    with path.open() as handle:
        for line in handle:
            raw = json.loads(line)
            yield ReplayEvent(
                event_type=raw["event_type"],
                received_ts=datetime.fromisoformat(raw["received_ts"]),
                payload=raw["payload"],
            )
