import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def logistic_baseline() -> Pipeline:
    return Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=1000))])


def gradient_boosting_baseline() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=100, random_state=42)


def time_split(frame: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    return frame.loc[frame.index <= cutoff], frame.loc[frame.index > cutoff]
