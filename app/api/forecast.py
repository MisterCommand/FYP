from functools import lru_cache

import numpy as np

from data import feature_frame

FLOOR = 1e-8


def design(frame, augmented):
    cols = ["history", "probability", "probability_change"] if augmented else ["history"]
    return np.column_stack([np.ones(len(frame)), frame[cols].to_numpy(float)])


@lru_cache
def forecast(horizon):
    frame = feature_frame(horizon).sort_values("date")
    predictions = {"baseline": [], "augmented": []}
    series = []
    # Daily expanding fit; labels must be fully observed strictly before origin.
    for row in frame.itertuples():
        train = frame[frame.target_end.lt(row.date)].dropna(subset=["target"])
        if len(train) < 60 or not np.isfinite(row.target):
            continue
        test = frame[frame.date.eq(row.date)]
        point = {"date": row.date.date().isoformat(), "realized": float(row.target)}
        for name in predictions:
            aug = name == "augmented"
            coef = np.linalg.lstsq(design(train, aug), train.target, rcond=None)[0]
            value = float(max(FLOOR, (design(test, aug) @ coef)[0]))
            predictions[name].append(value)
            point[name] = value
        series.append(point)
    latest = frame.tail(1)
    train = frame[frame.target_end.le(latest.iloc[0].date)].dropna(subset=["target"])
    metrics = {}
    actual = np.array([r["realized"] for r in series])
    for name, pred in predictions.items():
        pred = np.array(pred)
        ratio = np.maximum(actual, FLOOR) / pred
        coef = np.linalg.lstsq(design(train, name == "augmented"), train.target, rcond=None)[0]
        variance = float(max(FLOOR, (design(latest, name == "augmented") @ coef)[0]))
        metrics[name] = {"mse": float(np.mean((actual - pred)**2)),
                         "qlike": float(np.mean(ratio - np.log(ratio) - 1)),
                         "n": len(series), "latest_variance": variance,
                         "latest_volatility": float(np.sqrt(variance))}
    return {"asset": "SPY", "horizon": horizon, "target": "sum of next H squared daily log returns",
            "forecast_floor": FLOOR, "as_of": latest.iloc[0].date.date().isoformat(),
            "models": metrics, "series": series,
            "notes": "Identical test dates; 60 minimum training rows; daily expanding OLS; labels mature before test origin; volatility is horizon, not annualized. Latest is the last date with both event features."}
