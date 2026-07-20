from darwin.domain.signal import Signal


def average_scores(signals: list[Signal]) -> float:
    if not signals:
        return 0.0
    return sum(signal.score for signal in signals) / len(signals)
