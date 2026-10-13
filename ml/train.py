"""Model training script (M1.3 - M1.5) for FlowLens.

Performs top-20 feature selection, trains LightGBM multiclass classifier,
IsolationForest (on BENIGN flows only), and RandomForest baseline.
Produces all Contract 4.1 artifacts in models/.

Usage:
    python ml/train.py
"""
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest, RandomForestClassifier

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
SEED = 42

CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
LABEL_TO_ID = {c: i for i, c in enumerate(CLASSES)}
ID_TO_LABEL = {str(i): c for i, c in enumerate(CLASSES)}


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    train_path = PROCESSED_DIR / "train.parquet"
    val_path = PROCESSED_DIR / "val.parquet"
    test_path = PROCESSED_DIR / "test.parquet"

    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError("Processed datasets missing. Run `python ml/prepare.py` first.")

    print("Loading train and val parquet files...")
    train = pd.read_parquet(train_path)
    val = pd.read_parquet(val_path)

    # Encode integer labels 0..6
    train["y"] = train["label"].map(LABEL_TO_ID)
    val["y"] = val["label"].map(LABEL_TO_ID)

    # Non-feature columns: 'label', 'y', and 'dst_port' (Destination Port must NEVER be a feature)
    exclude_cols = {"label", "y", "dst_port", "Destination Port"}
    candidate_features = [col for col in train.columns if col not in exclude_cols]
    print(f"Candidate feature count: {len(candidate_features)}")

    # -------------------------------------------------------------
    # M1.4: Feature Reduction (Top 20 by LightGBM gain importance)
    # -------------------------------------------------------------
    print("\n--- M1.4: Feature Selection ---")
    initial_lgbm = LGBMClassifier(
        n_estimators=50,
        class_weight="balanced",
        importance_type="gain",
        random_state=SEED,
        verbose=-1,
    )
    initial_lgbm.fit(train[candidate_features], train["y"])
    importances = initial_lgbm.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    top_20_features = [candidate_features[i] for i in sorted_idx[:20]]

    print("Selected top 20 features by gain importance:")
    for rank, f in enumerate(top_20_features, 1):
        print(f"  {rank:2d}. {f} (gain: {importances[candidate_features.index(f)]:.2f})")

    # -------------------------------------------------------------
    # M1.5: Final Model Training
    # -------------------------------------------------------------
    print("\n--- M1.5: Training Final Models ---")

    # 1. LightGBM multiclass model (~200 trees)
    print("Training LightGBM classifier (200 trees, class_weight='balanced')...")
    lgbm = LGBMClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=SEED,
        verbose=-1,
    )
    lgbm.fit(train[top_20_features], train["y"])

    # 2. Isolation Forest on BENIGN train flows only
    benign_train = train.loc[train["y"] == 0, top_20_features]
    benign_val = val.loc[val["y"] == 0, top_20_features]
    print(f"Training IsolationForest on {len(benign_train):,} BENIGN flows (100 trees)...")
    iforest = IsolationForest(n_estimators=100, random_state=SEED)
    iforest.fit(benign_train)

    # Tune threshold on benign val flows for ~1% FPR (score_samples < threshold = anomaly)
    val_scores = iforest.score_samples(benign_val)
    threshold = float(np.quantile(val_scores, 0.01))
    val_fpr = float((val_scores < threshold).mean())
    print(f"Calibrated IsolationForest threshold: {threshold:.4f} (Benign Val FPR: {val_fpr:.3%})")

    # 3. Random Forest baseline (100 trees, n_jobs=-1)
    print("Training RandomForest baseline (100 trees)...")
    rf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=SEED)
    rf.fit(train[top_20_features], train["y"])

    # 4. Baselines: 101 percentiles (0 to 100) + 99.9th percentile per feature
    print("Computing benign baseline percentiles (102 values per feature)...")
    baselines = {}
    for f in top_20_features:
        pcts = [float(v) for v in np.percentile(benign_train[f], np.arange(101))]
        q99_9 = float(np.percentile(benign_train[f], 99.9))
        baselines[f] = pcts + [q99_9]

    # -------------------------------------------------------------
    # Save Artifacts (Contract 4.1)
    # -------------------------------------------------------------
    print("\nSaving artifacts to models/...")
    joblib.dump(lgbm, MODELS_DIR / "lgbm.joblib")
    joblib.dump(iforest, MODELS_DIR / "iforest.joblib")
    joblib.dump(rf, MODELS_DIR / "rf.joblib")

    (MODELS_DIR / "features.json").write_text(json.dumps(top_20_features, indent=2))
    (MODELS_DIR / "labels.json").write_text(json.dumps(ID_TO_LABEL, indent=2))
    (MODELS_DIR / "iforest_threshold.json").write_text(json.dumps({"threshold": threshold}, indent=2))
    (MODELS_DIR / "baselines.json").write_text(json.dumps(baselines))

    print("Successfully generated all models/* artifacts:")
    print("  - models/lgbm.joblib")
    print("  - models/iforest.joblib")
    print("  - models/rf.joblib")
    print("  - models/features.json")
    print("  - models/labels.json")
    print("  - models/iforest_threshold.json")
    print("  - models/baselines.json")

    # Quick test validation
    if test_path.exists():
        test = pd.read_parquet(test_path)
        test["y"] = test["label"].map(LABEL_TO_ID)
        test_acc = float((lgbm.predict(test[top_20_features]) == test["y"]).mean())
        print(f"\nQuick check: LightGBM test set accuracy = {test_acc:.3%}")


if __name__ == "__main__":
    main()
