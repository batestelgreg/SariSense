"""
Train the SariSense demand-forecasting model.

Run from the backend folder:

    python -m ml.train

Produces:  ml/forecast_model.pkl

The training set is a realistic synthetic dataset (20 products x 400 days)
that mimics sari-sari store behaviour: weekend lift, payday spikes and a
slow seasonal wave. Once a real store accumulates data you can extend
`load_series_from_db()` to train on live records instead.
"""
import os
from datetime import date, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from ml.engine import make_training_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE = os.path.join(BASE_DIR, "forecast_model.pkl")

DAYS = 400
N_PRODUCTS = 20


def synthetic_series(base_demand: float, seed: int) -> pd.Series:
    """One product, `DAYS` days of plausible daily sales."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(end=date.today(), periods=DAYS, freq="D")

    values = []
    for d in index:
        v = base_demand
        v *= 1.28 if d.dayofweek >= 5 else 1.0          # weekend lift
        v *= 1.45 if d.day in (15, 30, 31) else 1.0     # payday lift
        v *= 1.0 + 0.14 * np.sin(2 * np.pi * d.dayofyear / 365)  # seasonality
        v += rng.normal(0, max(0.4, base_demand * 0.20))
        values.append(max(0.0, round(v)))

    return pd.Series(values, index=index)


def main() -> None:
    print("Generating synthetic training data ...")
    series_list = [
        synthetic_series(base_demand=1.0 + (i * 1.4), seed=i)
        for i in range(N_PRODUCTS)
    ]

    X_all, y_all = [], []
    for s in series_list:
        X, y = make_training_matrix(s, min_history=14)
        X_all.append(X)
        y_all.append(y)

    X_all = np.vstack(X_all)
    y_all = np.concatenate(y_all)
    print(f"Training rows: {len(y_all):,}   features: {X_all.shape[1]}")

    # Hold out the last 20% of rows for an honest quality estimate.
    split = int(len(y_all) * 0.8)
    X_tr, X_te = X_all[:split], X_all[split:]
    y_tr, y_te = y_all[:split], y_all[split:]

    model = GradientBoostingRegressor(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.9,
        random_state=42,
    )
    print("Training GradientBoostingRegressor ...")
    model.fit(X_tr, y_tr)

    pred = np.clip(model.predict(X_te), 0, None)
    mae = float(mean_absolute_error(y_te, pred))
    mask = y_te > 0
    mape = float(np.mean(np.abs((y_te[mask] - pred[mask]) / y_te[mask])) * 100)

    print(f"Hold-out MAE : {mae:.3f} units/day")
    print(f"Hold-out MAPE: {mape:.2f} %")

    # Residual spread -> used for the confidence band on the dashboard.
    train_pred = np.clip(model.predict(X_tr), 0, None)
    residual_std = float(np.std(y_tr - train_pred))

    bundle = {
        "model": model,
        "residual_std": residual_std,
        "mae": round(mae, 3),
        "mape": round(mape, 2),
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_products": N_PRODUCTS,
        "features": list(model.feature_names_in_) if hasattr(model, "feature_names_in_") else None,
    }
    joblib.dump(bundle, MODEL_FILE, compress=3)
    print(f"Saved -> {MODEL_FILE}")


if __name__ == "__main__":
    main()
