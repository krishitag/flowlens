"""Write every contract 4.1 artifact from synthetic data, so the pipeline runs before the real models exist.

    python tests/make_fake_models.py

Overwrites models/* and data/processed/test.parquet. Never commit either.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
PROCESSED_DIR = ROOT / "data" / "processed"
SEED = 42

FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Mean", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Total", "Bwd Packets/s", "SYN Flag Count", "PSH Flag Count",
    "ACK Flag Count", "Average Packet Size", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
]
CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
ROWS_PER_CLASS = {"BENIGN": 2500, **{c: 420 for c in CLASSES[1:]}}

rng = np.random.default_rng(SEED)


def benign(n):
    """Skewed, heavy-tailed flows; several features are mostly zero (tests tied percentiles)."""
    def lognorm(mean, sigma):
        return rng.lognormal(mean, sigma, n)

    def mostly_zero(p_nonzero, values):
        return np.where(rng.random(n) < p_nonzero, values, 0)

    df = pd.DataFrame({
        "Flow Duration": lognorm(10, 2),
        "Total Fwd Packets": np.round(lognorm(1.5, 1)),
        "Total Backward Packets": np.round(lognorm(1.3, 1)),
        "Total Length of Fwd Packets": mostly_zero(0.7, np.round(lognorm(6, 1.5))),
        "Total Length of Bwd Packets": mostly_zero(0.6, np.round(lognorm(7, 1.5))),
        "Fwd Packet Length Max": np.round(lognorm(5, 1)),
        "Fwd Packet Length Mean": lognorm(4, 1),
        "Bwd Packet Length Mean": mostly_zero(0.6, lognorm(4.5, 1)),
        "Flow Bytes/s": lognorm(8, 2),
        "Flow Packets/s": lognorm(3, 1.5),
        "Flow IAT Mean": lognorm(9, 2),
        "Flow IAT Std": mostly_zero(0.5, lognorm(9, 2)),
        "Fwd IAT Total": mostly_zero(0.7, lognorm(10, 2)),
        "Bwd Packets/s": lognorm(2, 1.5),
        "SYN Flag Count": (rng.random(n) < 0.03).astype(float),
        "PSH Flag Count": (rng.random(n) < 0.3).astype(float),
        "ACK Flag Count": (rng.random(n) < 0.4).astype(float),
        "Average Packet Size": lognorm(4.5, 1),
        "Init_Win_bytes_forward": mostly_zero(0.6, rng.choice([8192, 29200, 65535], n)),
        "Init_Win_bytes_backward": mostly_zero(0.5, rng.choice([229, 1024, 65535], n)),
    })
    return df[FEATURES]


def attack(name, n):
    """Benign-looking flows with 2-3 features clearly shifted per class."""
    df = benign(n)
    if name == "DoS":
        df["Flow Duration"] *= 30
        df["Flow IAT Mean"] *= 30
        df["Bwd Packets/s"] *= 0.02
    elif name == "DDoS":
        df["Flow Packets/s"] *= 40
        df["Flow Bytes/s"] *= 40
        df["Total Fwd Packets"] = np.round(df["Total Fwd Packets"] * 10)
    elif name == "PortScan":
        df["SYN Flag Count"] = 1.0
        df["Total Length of Fwd Packets"] = 0.0
        df["Flow Duration"] *= 0.005
    elif name == "BruteForce":
        df["Init_Win_bytes_forward"] = 29200.0
        df["PSH Flag Count"] = 1.0
        df["Fwd Packet Length Mean"] *= 4
    elif name == "WebAttack":
        df["Total Length of Fwd Packets"] = np.round(rng.lognormal(10, 0.5, n))
        df["Fwd Packet Length Max"] *= 12
        df["Average Packet Size"] *= 6
    elif name == "Bot":
        df["Init_Win_bytes_backward"] = 237.0
        df["Flow IAT Std"] = rng.lognormal(13, 0.5, n)
        df["Total Backward Packets"] = np.round(df["Total Backward Packets"] * 6)
    return df


def main():
    parts = []
    for class_id, name in enumerate(CLASSES):
        n = ROWS_PER_CLASS[name]
        df = benign(n) if name == "BENIGN" else attack(name, n)
        df["y"] = class_id
        parts.append(df)
    data = pd.concat(parts, ignore_index=True)

    # 70 / 15 / 15 stratified, as in M1.2
    train, rest = train_test_split(data, test_size=0.3, stratify=data["y"], random_state=SEED)
    val, test = train_test_split(rest, test_size=0.5, stratify=rest["y"], random_state=SEED)

    lgbm = LGBMClassifier(n_estimators=50, random_state=SEED, verbose=-1)
    lgbm.fit(train[FEATURES], train["y"])

    benign_train = train.loc[train["y"] == 0, FEATURES]
    benign_val = val.loc[val["y"] == 0, FEATURES]
    iforest = IsolationForest(n_estimators=100, random_state=SEED)
    iforest.fit(benign_train)
    # score_samples below the threshold = anomalous; ~1% of benign val flows fall below it
    threshold = float(np.quantile(iforest.score_samples(benign_val), 0.01))

    baselines = {
        f: [float(v) for v in np.percentile(benign_train[f], np.arange(101))]
        + [float(np.percentile(benign_train[f], 99.9))]
        for f in FEATURES
    }

    test_out = test[FEATURES].reset_index(drop=True)
    test_out["label"] = [CLASSES[y] for y in test["y"]]
    test_out["dst_port"] = rng.integers(1, 65536, len(test_out))

    MODELS_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(lgbm, MODELS_DIR / "lgbm.joblib")
    joblib.dump(iforest, MODELS_DIR / "iforest.joblib")
    (MODELS_DIR / "features.json").write_text(json.dumps(FEATURES, indent=2))
    (MODELS_DIR / "labels.json").write_text(json.dumps({str(i): c for i, c in enumerate(CLASSES)}, indent=2))
    (MODELS_DIR / "iforest_threshold.json").write_text(json.dumps({"threshold": threshold}, indent=2))
    (MODELS_DIR / "baselines.json").write_text(json.dumps(baselines))
    test_out.to_parquet(PROCESSED_DIR / "test.parquet", index=False)

    acc = (lgbm.predict(test[FEATURES]) == test["y"]).mean()
    fpr = (iforest.score_samples(benign_val) < threshold).mean()
    print(f"wrote models/lgbm.joblib            (50 trees, test accuracy {acc:.3f})")
    print(f"wrote models/iforest.joblib         (100 trees, trained on {len(benign_train)} BENIGN rows)")
    print(f"wrote models/iforest_threshold.json (threshold {threshold:.4f}, benign val FPR {fpr:.3f})")
    print(f"wrote models/features.json          ({len(FEATURES)} features)")
    print(f"wrote models/labels.json            ({', '.join(CLASSES)})")
    print(f"wrote models/baselines.json         (102 values per feature)")
    print(f"wrote data/processed/test.parquet   ({len(test_out)} rows)")
    print(test_out["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
