import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelMetadata:
    model_id: str
    feature_schema_hash: str
    data_version: str
    features: list[str]


class ModelRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save_metadata(self, metadata: ModelMetadata) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{metadata.model_id}.json").write_text(
            json.dumps(metadata.__dict__, indent=2)
        )
