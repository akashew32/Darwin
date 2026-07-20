from datetime import UTC, datetime, timedelta

from darwin.backtest.walk_forward import rolling_folds


def test_rolling_folds_are_chronological() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    folds = rolling_folds(
        [start + timedelta(days=i) for i in range(10)], train_size=4, test_size=2, step=2
    )
    assert len(folds) == 3
    assert all(f.train_end < f.test_start for f in folds)
