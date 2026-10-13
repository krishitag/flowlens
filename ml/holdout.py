"""Leave-one-attack-out evaluation script (M1.7) for FlowLens.

Simulates unknown/zero-day attacks by retraining LightGBM without a target attack class,
then testing whether the hybrid architecture (LightGBM + IsolationForest) catches the attack.
Outputs:
  - reports/holdout.json
  - data/processed/holdout_<class>.parquet

Usage:
    python ml/holdout.py
"""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
SEED = 42

CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
LABEL_TO_ID = {c: i for i, c in enumerate(CLASSES)}


def evaluate_holdout(held_out_class, train_df, test_df, features, iforest, if_threshold):
    print(f"\n--- Running holdout for class: {held_out_class} ---")
    # 1. Save held-out test flows to data/processed/holdout_<class>.parquet
    held_out_flows = test_df[test_df["label"] == held_out_class].copy()
    out_parquet = PROCESSED_DIR / f"holdout_{held_out_class}.parquet"
    held_out_flows.to_parquet(out_parquet, index=False)
    print(f"Saved {len(held_out_flows)} held-out flows to {out_parquet}")

    # 2. Retrain LightGBM without this attack class
    train_filtered = train_df[train_df["label"] != held_out_class].copy()
    train_filtered["y"] = train_filtered["label"].map(LABEL_TO_ID)

    lgbm_holdout = LGBMClassifier(
        n_estimators=100,
        class_weight="balanced",
        random_state=SEED,
        verbose=-1,
    )
    lgbm_holdout.fit(train_filtered[features], train_filtered["y"])

    # 3. Test on held-out flows
    X_holdout = held_out_flows[features]
    n_flows = len(X_holdout)

    # LightGBM flag rule: predicts non-BENIGN (class != 0) with prob >= 0.5
    proba = lgbm_holdout.predict_proba(X_holdout)
    pred_class = proba.argmax(axis=1)
    pred_prob = proba[np.arange(n_flows), pred_class]
    lgbm_flagged = (pred_class != 0) & (pred_prob >= 0.5)

    # IsolationForest flag rule: score_samples < threshold
    if_scores = iforest.score_samples(X_holdout)
    iforest_flagged = (if_scores < if_threshold)

    # Either flag rule
    either_flagged = lgbm_flagged | iforest_flagged

    lgbm_recall = float(np.mean(lgbm_flagged))
    iforest_recall = float(np.mean(iforest_flagged))
    either_recall = float(np.mean(either_flagged))

    print(f"Results for {held_out_class}:")
    print(f"  LightGBM alone recall:        {lgbm_recall:.1%}")
    print(f"  IsolationForest alone recall: {iforest_recall:.1%}")
    print(f"  Either (Hybrid) recall:       {either_recall:.1%}")

    return {
        "lgbm_recall": lgbm_recall,
        "iforest_recall": iforest_recall,
        "either_recall": either_recall,
        "n_flows": n_flows,
    }


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    train = pd.read_parquet(PROCESSED_DIR / "train.parquet")
    test = pd.read_parquet(PROCESSED_DIR / "test.parquet")

    features = json.loads((MODELS_DIR / "features.json").read_text())
    iforest = joblib.load(MODELS_DIR / "iforest.joblib")
    if_threshold = json.loads((MODELS_DIR / "iforest_threshold.json").read_text())["threshold"]

    holdout_results = {}
    # Run Bot first, then WebAttack as specified in M1.7
    for attack_class in ["Bot", "WebAttack"]:
        holdout_results[attack_class] = evaluate_holdout(
            attack_class, train, test, features, iforest, if_threshold
        )

    out_json = REPORTS_DIR / "holdout.json"
    out_json.write_text(json.dumps(holdout_results, indent=2))
    print(f"\nSaved {out_json}")


if __name__ == "__main__":
    main()
