from functools import lru_cache

import numpy as np

from data import feature_frame

FLOOR = 1e-12
FLOOR_FRACTION = 0.01


def training_floor(train):
    return max(FLOOR, FLOOR_FRACTION * float(train.target.mean()))


def design(frame, augmented):
    cols = ["history", "probability", "probability_change"] if augmented else ["history"]
    return np.column_stack([np.ones(len(frame)), frame[cols].to_numpy(float)])


@lru_cache
def forecast(horizon):
    frame = feature_frame(horizon).sort_values("date")
    predictions = {"baseline": [], "augmented": []}
    floor_hits = {name: 0 for name in predictions}
    series = []
    # Daily expanding fit; labels must be fully observed strictly before origin.
    for row in frame.itertuples():
        train = frame[frame.target_end.lt(row.date)].dropna(subset=["target"])
        if len(train) < 60 or not np.isfinite(row.target):
            continue
        test = frame[frame.date.eq(row.date)]
        floor = training_floor(train)
        point = {"date": row.date.date().isoformat(), "realized": float(row.target), "floor": floor}
        for name in predictions:
            aug = name == "augmented"
            coef = np.linalg.lstsq(design(train, aug), train.target, rcond=None)[0]
            raw = float((design(test, aug) @ coef)[0])
            value = max(floor, raw)
            floor_hits[name] += int(raw <= floor)
            predictions[name].append(value)
            point[name] = value
        series.append(point)
    latest = frame.tail(1)
    train = frame[frame.target_end.le(latest.iloc[0].date)].dropna(subset=["target"])
    metrics = {}
    latest_floor = training_floor(train)
    actual = np.array([r["realized"] for r in series])
    for name, pred in predictions.items():
        pred = np.array(pred)
        ratio = np.maximum(actual, FLOOR) / pred
        coef = np.linalg.lstsq(design(train, name == "augmented"), train.target, rcond=None)[0]
        raw = float((design(latest, name == "augmented") @ coef)[0])
        variance = max(latest_floor, raw)
        metrics[name] = {"mse": float(np.mean((actual - pred)**2)),
                         "qlike": float(np.mean(ratio - np.log(ratio) - 1)),
                         "n": len(series), "floor_hits": floor_hits[name], "latest_floor_hit": raw <= latest_floor,
                         "latest_variance": variance,
                         "latest_volatility": float(np.sqrt(variance))}
    return {"asset": "SPY", "horizon": horizon, "target": "sum of next H squared daily log returns",
            "forecast_floor": latest_floor,
            "floor_policy": "Pre-specified max(1e-12, 1% of each expanding training sample's mean RV); floor_hits counts out-of-sample raw predictions at/below that floor.",
            "as_of": latest.iloc[0].date.date().isoformat(),
            "models": metrics, "series": series,
            "notes": "Identical test dates; 60 minimum training rows; daily expanding OLS; labels mature before test origin; volatility is horizon, not annualized. Latest is the last date with both event features."}
