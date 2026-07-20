import pandas as pd


def leakage_safe_returns(prices: pd.Series, horizon: int) -> pd.Series:
    return prices.pct_change(periods=horizon).fillna(0)


def ewma_crossover(prices: pd.Series, fast_span: int, slow_span: int) -> pd.Series:
    fast = prices.ewm(span=fast_span, adjust=False).mean()
    slow = prices.ewm(span=slow_span, adjust=False).mean()
    return (fast - slow).fillna(0)
