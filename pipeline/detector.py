"""Tier-2 detector (M2.4): scores a window with LightGBM (+ IsolationForest when ELEVATED) and applies the flag rule.

    python -m pipeline.detector
"""
import json
import time
from pathlib import Path

import joblib
import numpy as np


class Detector:
    def __init__(self, models_dir="models", normal_sample=0.1, seed=0):
        models_dir = Path(models_dir)
        self.features = json.loads((models_dir / "features.json").read_text())
        labels = json.loads((models_dir / "labels.json").read_text())
        self.threshold = json.loads((models_dir / "iforest_threshold.json").read_text())["threshold"]
        self.lgbm = joblib.load(models_dir / "lgbm.joblib")
        self.iforest = joblib.load(models_dir / "iforest.joblib")
        # predict_proba columns follow lgbm.classes_ (ids like 0..6, or names if trained on strings)
        self.col_label = np.array([labels.get(str(c), str(c)) for c in self.lgbm.classes_])
        self.normal_sample = normal_sample
        self.rng = np.random.default_rng(seed)

    def detect(self, window_df, state):
        """Return (flagged_df, scored_count).

        NORMAL: a random `normal_sample` share of flows, LightGBM only.
        ELEVATED: every flow, LightGBM and IsolationForest.
        Flagged rows get pred_label, pred_prob, if_score, source, detect_ms.
        """
        elevated = state == "ELEVATED"
        if elevated:
            scored = window_df
        else:
            k = round(len(window_df) * self.normal_sample)
            scored = window_df.iloc[np.sort(self.rng.choice(len(window_df), k, replace=False))]
        n = len(scored)
        if n == 0:
            return window_df.iloc[:0].copy(), 0

        X = scored[self.features]
        start = time.perf_counter()
        proba = self.lgbm.predict_proba(X)
        if_score = self.iforest.score_samples(X) if elevated else np.full(n, np.nan)
        detect_ms = (time.perf_counter() - start) * 1000 / n

        cols = proba.argmax(axis=1)
        pred_label = self.col_label[cols]
        pred_prob = proba[np.arange(n), cols]

        lgbm_flag = (pred_label != "BENIGN") & (pred_prob >= 0.5)
        if_flag = if_score < self.threshold  # NaN compares False
        source = np.where(lgbm_flag & if_flag, "both", np.where(lgbm_flag, "lgbm", "iforest"))

        mask = lgbm_flag | if_flag
        flagged = scored[mask].copy()
        flagged["pred_label"] = pred_label[mask]
        flagged["pred_prob"] = pred_prob[mask]
        flagged["if_score"] = if_score[mask]
        flagged["source"] = source[mask]
        flagged["detect_ms"] = detect_ms
        return flagged, n


if __name__ == "__main__":
    import pandas as pd

    test = pd.read_parquet("data/processed/test.parquet").reset_index(drop=True)
    rng = np.random.default_rng(0)
    idx = np.concatenate([
        rng.choice(test.index[test["label"] == "DoS"], 280),
        rng.choice(test.index[test["label"] == "BENIGN"], 120),
    ])
    window = test.iloc[idx].reset_index(drop=True)
    window["flow_idx"] = idx

    detector = Detector()
    for state in ["ELEVATED", "NORMAL"]:
        flagged, scored = detector.detect(window, state)
        print(f"\n=== {state}: {len(window)} flows, scored {scored}, flagged {len(flagged)} ===")
        if len(flagged):
            print(f"detect_ms per flow: {flagged['detect_ms'].iloc[0]:.4f}")
            print("by source:    ", flagged["source"].value_counts().to_dict())
            print("by pred_label:", flagged["pred_label"].value_counts().to_dict())
            print("by true label:", flagged["label"].value_counts().to_dict())
