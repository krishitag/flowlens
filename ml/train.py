"""M1.3-M1.5: train LightGBM, IsolationForest and the RF baseline, and write every contract 4.1 file.

Usage: python ml/train.py
Reads data/processed/{train,val}.parquet, writes models/*.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"

SEED = 0
N_TOP = 20
CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
NON_FEATURES = ["label", "dst_port"]  # dst_port leaks the answer: never a feature


def train_lgbm(X, y):
    # max_bin=1023: the default 255 histogram bins are too coarse to separate WebAttack from BENIGN
    # (val WebAttack F1 0.85 -> 0.95); 16383 bins made training diverge
    model = LGBMClassifier(n_estimators=200, max_bin=1023, class_weight="balanced", random_state=SEED, verbose=-1)
    model.fit(X, y)
    return model


def macro_f1(model, X, y):
    return f1_score(y, model.predict(X), average="macro")


def main():
    train = pd.read_parquet(DATA_DIR / "train.parquet")
    val = pd.read_parquet(DATA_DIR / "val.parquet")
    class_id = {c: i for i, c in enumerate(CLASSES)}
    y_train = train["label"].map(class_id).to_numpy()
    y_val = val["label"].map(class_id).to_numpy()

    all_features = [c for c in train.columns if c not in NON_FEATURES]
    print(f"train {len(train):,} rows, val {len(val):,} rows, {len(all_features)} features")

    # M1.3: LightGBM on all features
    lgbm_all = train_lgbm(train[all_features], y_train)
    f1_all = macro_f1(lgbm_all, val[all_features], y_val)
    print(f"LightGBM, {len(all_features)} features: val macro F1 {f1_all:.4f}")

    # M1.4: keep the top 20 by gain importance and retrain
    gain = lgbm_all.booster_.feature_importance(importance_type="gain")
    order = np.argsort(gain)[::-1][:N_TOP]
    features = [all_features[i] for i in order]
    lgbm = train_lgbm(train[features], y_train)
    f1_top = macro_f1(lgbm, val[features], y_val)
    print(f"LightGBM, {N_TOP} features: val macro F1 {f1_top:.4f} ({(f1_top - f1_all) * 100:+.2f} points)")

    # IsolationForest on BENIGN train only; score_samples below the threshold = anomalous
    benign_train = train.loc[train["label"] == "BENIGN", features]
    benign_val = val.loc[val["label"] == "BENIGN", features]
    iforest = IsolationForest(n_estimators=100, random_state=SEED)
    iforest.fit(benign_train)
    threshold = float(np.quantile(iforest.score_samples(benign_val), 0.01))
    fpr = (iforest.score_samples(benign_val) < threshold).mean()
    print(f"IsolationForest: threshold {threshold:.4f}, benign val FPR {fpr:.4f}")

    # RF baseline (not used by the pipeline)
    rf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=SEED)
    rf.fit(train[features], y_train)
    print(f"RandomForest, {N_TOP} features: val macro F1 {macro_f1(rf, val[features], y_val):.4f}")

    # 101 BENIGN train percentiles + the 99.9th as the last element
    baselines = {
        f: [float(v) for v in np.percentile(benign_train[f], np.arange(101))]
        + [float(np.percentile(benign_train[f], 99.9))]
        for f in features
    }

    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(lgbm, MODELS_DIR / "lgbm.joblib")
    joblib.dump(iforest, MODELS_DIR / "iforest.joblib")
    joblib.dump(rf, MODELS_DIR / "rf.joblib")
    (MODELS_DIR / "features.json").write_text(json.dumps(features, indent=2))
    (MODELS_DIR / "labels.json").write_text(json.dumps({str(i): c for i, c in enumerate(CLASSES)}, indent=2))
    (MODELS_DIR / "iforest_threshold.json").write_text(json.dumps({"threshold": threshold}, indent=2))
    (MODELS_DIR / "baselines.json").write_text(json.dumps(baselines))
    print(f"\nwrote models/: lgbm, iforest, rf, features ({N_TOP}), labels, iforest_threshold, baselines")


if __name__ == "__main__":
    main()
