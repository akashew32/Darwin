import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class KillSwitch:
    path: Path

    def active(self) -> bool:
        return self.path.exists()

    def activate(self, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"active": True, "reason": reason, "ts": datetime.now(UTC).isoformat()})
        )

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
