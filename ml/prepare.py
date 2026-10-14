"""M1.2: clean CIC-IDS2017 MachineLearningCSV and write stratified train/val/test splits.

Usage: python ml/prepare.py
Reads data/raw/*.csv, writes data/processed/{train,val,test}.parquet.
Output columns: every feature column + `label` (grouped class, contract 4.2) + `dst_port`.
`dst_port` is kept for the dashboard only and must never be used as a model feature.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

SEED = 42
BENIGN_CAP = 300_000
ATTACK_CAP = 50_000

# Contract 4.2. Web Attack labels contain a mangled dash byte, so they're matched by prefix below.
LABEL_MAP = {
    "BENIGN": "BENIGN",
    "DoS Hulk": "DoS",
    "DoS GoldenEye": "DoS",
    "DoS slowloris": "DoS",
    "DoS Slowhttptest": "DoS",
    "DDoS": "DDoS",
    "PortScan": "PortScan",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
    "Bot": "Bot",
}
DROP_LABELS = {"Infiltration", "Heartbleed"}

# Not in MachineLearningCSV, but present in the TrafficLabelling variant some mirrors ship. Never features.
ID_COLUMNS = ["Flow ID", "Source IP", "Source Port", "Destination IP", "Timestamp"]


def group_label(raw):
    raw = raw.strip()
    if raw.startswith("Web Attack"):
        return "WebAttack"
    if raw in DROP_LABELS:
        return None
    if raw not in LABEL_MAP:
        raise ValueError(f"unknown label: {raw!r}")
    return LABEL_MAP[raw]


def load_csv(path):
    # latin-1 because the Web Attack labels contain a non-UTF-8 byte
    df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = df.columns.str.strip()
    # `Fwd Header Length` appears twice; pandas renames the second to `Fwd Header Length.1`
    df = df.drop(columns=["Fwd Header Length.1"], errors="ignore")
    df = df.loc[:, ~df.columns.duplicated()]
    df = df.drop(columns=[c for c in ID_COLUMNS if c in df.columns])
    df = df.rename(columns={"Destination Port": "dst_port", "Label": "label"})

    df["label"] = df["label"].astype(str).map(group_label)
    df = df[df["label"].notna()]

    features = [c for c in df.columns if c not in ("label", "dst_port")]
    df[features] = df[features].apply(pd.to_numeric, errors="coerce")
    df[features] = df[features].replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    df[features] = df[features].astype("float32")
    df["dst_port"] = df["dst_port"].astype("int32")
    return df


def sample_caps(df):
    parts = []
    for label, group in df.groupby("label"):
        cap = BENIGN_CAP if label == "BENIGN" else ATTACK_CAP
        parts.append(group.sample(n=min(cap, len(group)), random_state=SEED))
    return pd.concat(parts, ignore_index=True)


def main():
    paths = sorted(RAW_DIR.glob("*.csv"))
    if not paths:
        raise SystemExit(f"No CSVs in {RAW_DIR}. Download CIC-IDS2017 MachineLearningCSV first (M1.1).")

    frames = []
    for path in paths:
        df = load_csv(path)
        print(f"loaded {path.name}: {len(df):,} rows")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    before = len(df)
    df = df.drop_duplicates(ignore_index=True)
    print(f"\ndropped {before - len(df):,} duplicate rows, {len(df):,} left")
    print("\nclass counts after cleaning:")
    print(df["label"].value_counts().to_string())

    df = sample_caps(df)

    # Stratified 70/15/15: split off 30%, then halve it into val and test.
    train, rest = train_test_split(df, test_size=0.30, stratify=df["label"], random_state=SEED)
    val, test = train_test_split(rest, test_size=0.50, stratify=rest["label"], random_state=SEED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, split in [("train", train), ("val", val), ("test", test)]:
        split = split.reset_index(drop=True)
        split.to_parquet(OUT_DIR / f"{name}.parquet", index=False)
        counts[name] = split["label"].value_counts()

    n_features = len([c for c in df.columns if c not in ("label", "dst_port")])
    print(f"\nwrote {OUT_DIR}/{{train,val,test}}.parquet ({n_features} feature columns + label + dst_port)")
    print("\nclass counts per split:")
    table = pd.DataFrame(counts).fillna(0).astype(int)
    table.loc["TOTAL"] = table.sum()
    print(table.to_string())


if __name__ == "__main__":
    main()
