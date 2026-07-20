from datetime import timedelta


def milliseconds(value: int) -> timedelta:
    return timedelta(milliseconds=value)
