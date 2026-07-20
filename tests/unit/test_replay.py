from datetime import UTC, datetime

from darwin.data.replay import ReplayEvent, read_replay, write_replay


def test_replay_round_trip_is_deterministic(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    events = [ReplayEvent("snapshot", datetime(2026, 1, 1, tzinfo=UTC), {"seq": 1})]
    write_replay(path, events)
    assert list(read_replay(path)) == events
