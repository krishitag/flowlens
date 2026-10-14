"""M1.7: leave-one-attack-out. Retrain LightGBM without one attack class and see what still catches it.

Usage: python ml/holdout.py
For each held-out class, on that class's test flows:
- LightGBM alone: any non-BENIGN prediction counts as caught
- IForest alone: score_samples < threshold (the production IForest; it never sees attack labels)
- either: caught by one or both
Writes reports/holdout.json and data/processed/holdout_<class>.parquet.
"""
import json
from pathlib import Path

import joblib
import pandas as pd

from train import CLASSES, train_lgbm

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"

HOLDOUT_CLASSES = ["DoS", "Bot"]


def main():
    features = json.loads((MODELS_DIR / "features.json").read_text())
    iforest = joblib.load(MODELS_DIR / "iforest.joblib")
    threshold = json.loads((MODELS_DIR / "iforest_threshold.json").read_text())["threshold"]
    train = pd.read_parquet(DATA_DIR / "train.parquet")
    test = pd.read_parquet(DATA_DIR / "test.parquet")
    class_id = {c: i for i, c in enumerate(CLASSES)}

    results = {}
    for held_out in HOLDOUT_CLASSES:
        kept = train[train["label"] != held_out]
        lgbm = train_lgbm(kept[features], kept["label"].map(class_id).to_numpy())

        flows = test[test["label"] == held_out].reset_index(drop=True)
        flows.to_parquet(DATA_DIR / f"holdout_{held_out}.parquet", index=False)

        pred = lgbm.predict(flows[features])
        lgbm_hit = pred != class_id["BENIGN"]
        iforest_hit = iforest.score_samples(flows[features]) < threshold
        predicted_as = pd.Series(pred).map(dict(enumerate(CLASSES))).value_counts()

        results[held_out] = {
            "lgbm_recall": float(lgbm_hit.mean()),
            "iforest_recall": float(iforest_hit.mean()),
            "either_recall": float((lgbm_hit | iforest_hit).mean()),
            "n_flows": len(flows),
            "lgbm_predicted_as": {c: int(n) for c, n in predicted_as.items()},
        }
        r = results[held_out]
        print(f"{held_out} held out ({r['n_flows']:,} test flows): LightGBM {r['lgbm_recall']:.3f}, "
              f"IForest {r['iforest_recall']:.3f}, either {r['either_recall']:.3f}")
        print(f"    LightGBM predicted them as: {r['lgbm_predicted_as']}")

    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "holdout.json").write_text(json.dumps(results, indent=2))
    print(f"\nwrote reports/holdout.json, data/processed/holdout_{{{','.join(HOLDOUT_CLASSES)}}}.parquet")


if __name__ == "__main__":
    main()
