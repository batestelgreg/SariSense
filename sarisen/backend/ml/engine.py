"""
SariSense ML engine
===================
Two models live here:

1. Demand forecasting  -> GradientBoostingRegressor (scikit-learn)
2. Anomaly detection   -> IsolationForest (scikit-learn)

The forecasting model is trained ONCE (see ml/train.py) and saved to
forecast_model.pkl. The API loads it at startup and only *scores* it,
which keeps Render's free 512 MB instance fast and stable.
"""
import os
from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, "forecast_model.pkl")

FEATURES = [
    "dow", "dom", "is_weekend", "is_payday",
    "lag_7", "lag_14", "roll_7", "roll_28", "prod_avg",
]

_bundle = None
_bundle_loaded = False


# ---------------------------------------------------------------------
# Model loading (cached - loaded once per process)
# ---------------------------------------------------------------------
def load_bundle():
    global _bundle, _bundle_loaded
    if not _bundle_loaded:
        _bundle = joblib.load(MODEL_FILE) if os.path.exists(MODEL_FILE) else None
        _bundle_loaded = True
    return _bundle


def reload_bundle():
    global _bundle, _bundle_loaded
    _bundle_loaded = False
    return load_bundle()


def model_info():
    bundle = load_bundle()
    if bundle is None:
        return {"loaded": False, "model": None}
    return {
        "loaded": True,
        "model": "GradientBoostingRegressor",
        "trained_at": bundle.get("trained_at"),
        "mape": bundle.get("mape"),
        "mae": bundle.get("mae"),
        "products_in_training": bundle.get("n_products"),
    }


# ---------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------
def build_series(rows, days=120, end=None):
    """
    Turn DB rows [{sold_at, quantity}] into a dense daily pandas Series.
    Missing days become 0 - important, because a day with no sale is a
    real signal, not a missing value.
    """
    end_ts = pd.Timestamp(end or date.today()).normalize()
    start_ts = end_ts - pd.Timedelta(days=days - 1)
    index = pd.date_range(start_ts, end_ts, freq="D")

    if not rows:
        return pd.Series(0.0, index=index)

    data = {
        pd.Timestamp(r["sold_at"]).normalize(): float(r["quantity"])
        for r in rows
    }
    return pd.Series(data).reindex(index, fill_value=0.0).astype(float)


def _feature_row(series: pd.Series, day: pd.Timestamp):
    """One feature vector for `day`, using only information from before it."""
    past = series[series.index < day]
    avg = float(past.mean()) if len(past) else 0.0

    def lag(n):
        t = day - pd.Timedelta(days=n)
        return float(series[t]) if t in series.index else avg

    roll7 = float(past.tail(7).mean()) if len(past) else 0.0
    roll28 = float(past.tail(28).mean()) if len(past) else 0.0

    return [
        day.dayofweek,
        day.day,
        int(day.dayofweek >= 5),      # weekend
        int(day.day in (15, 30, 31)),  # payday window
        lag(7),
        lag(14),
        roll7,
        roll28,
        avg,
    ]


def make_training_matrix(series: pd.Series, min_history: int = 14):
    X, y = [], []
    for i in range(min_history, len(series)):
        day = series.index[i]
        X.append(_feature_row(series, day))
        y.append(float(series.iloc[i]))
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


# ---------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------
def _naive_forecast(series, horizon):
    """Fallback used when the trained model is not present."""
    baseline = float(series.tail(14).mean()) if len(series) else 0.0
    out = []
    for i in range(horizon):
        d = series.index[-1] + pd.Timedelta(days=i + 1)
        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "predicted": round(baseline, 2),
            "lower": round(max(0.0, baseline * 0.6), 2),
            "upper": round(baseline * 1.4, 2),
        })
    return out


def forecast_product(series: pd.Series, horizon: int = 7):
    """
    Recursive multi-step forecast. Each predicted day is fed back in as
    history for the next day, which is how real demand models roll forward.
    """
    bundle = load_bundle()
    if bundle is None:
        return _naive_forecast(series, horizon)

    model = bundle["model"]
    sigma = float(bundle.get("residual_std", 0.0))

    working = series.copy()
    predictions = []

    for _ in range(horizon):
        day = working.index[-1] + pd.Timedelta(days=1)
        row = np.asarray([_feature_row(working, day)], dtype=float)
        value = max(0.0, float(model.predict(row)[0]))

        predictions.append({
            "date": day.strftime("%Y-%m-%d"),
            "predicted": round(value, 2),
            "lower": round(max(0.0, value - 1.28 * sigma), 2),   # ~80% band
            "upper": round(value + 1.28 * sigma, 2),
        })
        working.loc[day] = value

    return predictions


# ---------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------
def detect_anomalies(series: pd.Series, lookback: int = 30):
    """
    IsolationForest on [daily quantity, 7-day rolling mean].
    Returns unusual days only (spikes and drops).
    """
    if len(series) < 21:
        return []

    frame = pd.DataFrame({"qty": series.astype(float)})
    frame["roll7"] = frame["qty"].rolling(7, min_periods=1).mean()

    X = frame[["qty", "roll7"]].to_numpy(dtype=float)
    forest = IsolationForest(
        n_estimators=120, contamination=0.05, random_state=42
    ).fit(X)

    frame["flag"] = forest.predict(X)
    frame["score"] = forest.decision_function(X)

    findings = []
    for ts, row in frame.tail(lookback).iterrows():
        if row["flag"] != -1:
            continue

        qty = float(row["qty"])
        expected = float(row["roll7"])
        gap = abs(qty - expected)
        direction = "spike" if qty > expected else "drop"

        # IsolationForest marks ~5% of days by design. Require a real
        # deviation on top of that so the owner is not spammed with noise.
        if gap < max(2.0, expected * 0.40):
            continue

        severity = "high" if gap >= max(4.0, expected * 0.8) else "medium"

        findings.append({
            "date": ts.strftime("%Y-%m-%d"),
            "quantity": round(qty, 1),
            "expected": round(expected, 1),
            "direction": direction,
            "severity": severity,
            "score": round(float(row["score"]), 4),
            "message": (
                f"Unusual {direction}: {qty:.0f} unit(s) sold vs "
                f"~{expected:.1f} expected."
            ),
        })

    findings.sort(key=lambda f: f["date"], reverse=True)
    return findings
