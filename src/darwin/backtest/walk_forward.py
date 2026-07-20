from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


def rolling_folds(
    times: list[datetime], train_size: int, test_size: int, step: int
) -> list[WalkForwardFold]:
    ordered = sorted(times)
    folds: list[WalkForwardFold] = []
    start = 0
    while start + train_size + test_size <= len(ordered):
        folds.append(
            WalkForwardFold(
                train_start=ordered[start],
                train_end=ordered[start + train_size - 1],
                test_start=ordered[start + train_size],
                test_end=ordered[start + train_size + test_size - 1],
            )
        )
        start += step
    return folds
