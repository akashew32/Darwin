import pandas as pd


def make_direction_label(prices: pd.Series, horizon: int, threshold: float) -> pd.Series:
    future = prices.shift(-horizon)
    return ((future - prices) > threshold).astype(int)
