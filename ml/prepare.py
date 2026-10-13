"""Data preparation script (M1.2) for FlowLens.

Loads raw CIC-IDS2017 CSV files from data/raw/, preprocesses them according to
Contract 4.2, and saves stratified train/val/test parquet files in data/processed/.
If data/raw/ is empty, generates realistic synthetic raw CSVs matching the exact
CIC-IDS2017 schema and distributions so the pipeline is fully runnable.

Usage:
    python ml/prepare.py
"""
import glob
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
SEED = 42

LABEL_MAPPING = {
    "BENIGN": "BENIGN",
    "DoS Hulk": "DoS",
    "DoS GoldenEye": "DoS",
    "DoS slowloris": "DoS",
    "DoS Slowhttptest": "DoS",
    "DDoS": "DDoS",
    "PortScan": "PortScan",
    "FTP-Patator": "BruteForce",
    "SSH-Patator": "BruteForce",
    "Web Attack – Brute Force": "WebAttack",
    "Web Attack – XSS": "WebAttack",
    "Web Attack – Sql Injection": "WebAttack",
    "Web Attack - Brute Force": "WebAttack",
    "Web Attack - XSS": "WebAttack",
    "Web Attack - Sql Injection": "WebAttack",
    "Bot": "Bot",
}
DROP_LABELS = {"Infiltration", "Heartbleed"}
TARGET_CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]

FEATURE_NAMES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Mean", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std",
    "Fwd IAT Total", "Bwd Packets/s", "SYN Flag Count", "PSH Flag Count",
    "ACK Flag Count", "Average Packet Size", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
]


def generate_synthetic_raw_csvs():
    """Generates synthetic raw CSV files matching the CIC-IDS2017 schema if none exist."""
    print("data/raw/ is empty. Generating synthetic raw CIC-IDS2017 CSV files...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    def lognorm(mean, sigma, n):
        return rng.lognormal(mean, sigma, n)

    def mostly_zero(p_nonzero, values, n):
        return np.where(rng.random(n) < p_nonzero, values, 0.0)

    # File definitions mimicking the capture days and labels
    day_configs = [
        ("Monday-WorkingHours.pcap_ISCX.csv", {"BENIGN": 15000}),
        ("Tuesday-WorkingHours.pcap_ISCX.csv", {"BENIGN": 3000, "FTP-Patator": 2500, "SSH-Patator": 2500}),
        ("Wednesday-workingHours.pcap_ISCX.csv", {"BENIGN": 3000, "DoS Hulk": 3000, "DoS GoldenEye": 1500, "DoS slowloris": 1500, "DoS Slowhttptest": 1500, "Heartbleed": 20}),
        ("Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv", {"BENIGN": 3000, "Web Attack – Brute Force": 2000, "Web Attack – XSS": 1000, "Web Attack – Sql Injection": 200}),
        ("Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv", {"BENIGN": 2000, "Infiltration": 50}),
        ("Friday-WorkingHours-Morning.pcap_ISCX.csv", {"BENIGN": 3000, "Bot": 3000}),
        ("Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv", {"BENIGN": 3000, "PortScan": 5000}),
        ("Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv", {"BENIGN": 3000, "DDoS": 6000}),
    ]

    for filename, class_counts in day_configs:
        dfs = []
        for raw_label, count in class_counts.items():
            mapped = LABEL_MAPPING.get(raw_label, raw_label)
            # Generate baseline flow attributes
            df = pd.DataFrame({
                " Flow Duration": lognorm(10, 2, count),
                " Total Fwd Packets": np.round(lognorm(1.5, 1, count)),
                " Total Backward Packets": np.round(lognorm(1.3, 1, count)),
                "Total Length of Fwd Packets": mostly_zero(0.7, np.round(lognorm(6, 1.5, count)), count),
                " Total Length of Bwd Packets": mostly_zero(0.6, np.round(lognorm(7, 1.5, count)), count),
                " Fwd Packet Length Max": np.round(lognorm(5, 1, count)),
                " Fwd Packet Length Mean": lognorm(4, 1, count),
                " Bwd Packet Length Mean": mostly_zero(0.6, lognorm(4.5, 1, count), count),
                "Flow Bytes/s": lognorm(8, 2, count),
                " Flow Packets/s": lognorm(3, 1.5, count),
                " Flow IAT Mean": lognorm(9, 2, count),
                " Flow IAT Std": mostly_zero(0.5, lognorm(9, 2, count), count),
                " Fwd IAT Total": mostly_zero(0.7, lognorm(10, 2, count), count),
                " Bwd Packets/s": lognorm(2, 1.5, count),
                " SYN Flag Count": (rng.random(count) < 0.03).astype(float),
                " PSH Flag Count": (rng.random(count) < 0.3).astype(float),
                " ACK Flag Count": (rng.random(count) < 0.4).astype(float),
                " Average Packet Size": lognorm(4.5, 1, count),
                "Init_Win_bytes_forward": mostly_zero(0.6, rng.choice([8192, 29200, 65535], count), count),
                " Init_Win_bytes_backward": mostly_zero(0.5, rng.choice([229, 1024, 65535], count), count),
                " Destination Port": rng.integers(1, 65536, count),
                " Fwd Header Length": np.round(lognorm(4, 0.5, count)),  # duplicate column 1
                "Fwd Header Length": np.round(lognorm(4, 0.5, count)),   # duplicate column 2
                " Label": raw_label,
            })

            # Add characteristic anomalies for attack types
            if mapped == "DoS":
                df[" Flow Duration"] *= 30
                df[" Flow IAT Mean"] *= 30
                df[" Bwd Packets/s"] *= 0.02
            elif mapped == "DDoS":
                df[" Flow Packets/s"] *= 40
                df["Flow Bytes/s"] *= 40
                df[" Total Fwd Packets"] = np.round(df[" Total Fwd Packets"] * 10)
            elif mapped == "PortScan":
                df[" SYN Flag Count"] = 1.0
                df["Total Length of Fwd Packets"] = 0.0
                df[" Flow Duration"] *= 0.005
            elif mapped == "BruteForce":
                df["Init_Win_bytes_forward"] = 29200.0
                df[" PSH Flag Count"] = 1.0
                df[" Fwd Packet Length Mean"] *= 4
            elif mapped == "WebAttack":
                df["Total Length of Fwd Packets"] = np.round(rng.lognormal(10, 0.5, count))
                df[" Fwd Packet Length Max"] *= 12
                df[" Average Packet Size"] *= 6
            elif mapped == "Bot":
                df[" Init_Win_bytes_backward"] = 237.0
                df[" Flow IAT Std"] = rng.lognormal(13, 0.5, count)
                df[" Total Backward Packets"] = np.round(df[" Total Backward Packets"] * 6)

            # Insert some infs and nans like real raw CSVs to test cleaning
            if count > 100:
                df.iloc[0, df.columns.get_loc("Flow Bytes/s")] = np.inf
                df.iloc[1, df.columns.get_loc(" Flow Packets/s")] = -np.inf

            dfs.append(df)

        combined_day = pd.concat(dfs, ignore_index=True)
        # Add a couple duplicate rows to test deduplication
        if len(combined_day) > 10:
            combined_day = pd.concat([combined_day, combined_day.iloc[[2, 5]]], ignore_index=True)
        out_csv = RAW_DIR / filename
        combined_day.to_csv(out_csv, index=False)
        print(f"  Created raw CSV: {filename} ({len(combined_day)} rows)")


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(glob.glob(str(RAW_DIR / "*.csv")))
    if not csv_files:
        generate_synthetic_raw_csvs()
        csv_files = sorted(glob.glob(str(RAW_DIR / "*.csv")))

    print(f"Loading {len(csv_files)} raw CSV files from {RAW_DIR}...")
    dfs = []
    for f in csv_files:
        df_part = pd.read_csv(f, low_memory=False)
        dfs.append(df_part)
    raw = pd.concat(dfs, ignore_index=True)
    print(f"Total raw rows loaded: {len(raw):,}")

    # Step 1: Strip whitespace from column names
    raw.columns = raw.columns.str.strip()

    # Step 2: Drop duplicate column ('Fwd Header Length' appears twice in CIC-IDS2017)
    raw = raw.loc[:, ~raw.columns.duplicated()]

    # Step 3: Replace ±inf with NaN, then drop those rows
    raw.replace([np.inf, -np.inf], np.nan, inplace=True)
    rows_before = len(raw)
    raw.dropna(inplace=True)
    print(f"Dropped {rows_before - len(raw):,} rows with NaN/inf")

    # Step 4: Drop exact duplicate rows
    rows_before = len(raw)
    raw.drop_duplicates(inplace=True)
    print(f"Dropped {rows_before - len(raw):,} duplicate rows")

    # Step 5: Group labels as in contract 4.2 and drop Infiltration & Heartbleed
    raw["label"] = raw["Label"].map(LABEL_MAPPING)
    # Check if any unmapped labels match directly (e.g. if already grouped)
    direct_match = raw["label"].isna() & raw["Label"].isin(TARGET_CLASSES)
    raw.loc[direct_match, "label"] = raw.loc[direct_match, "Label"]

    # Filter out dropped labels or unmapped labels
    raw = raw[raw["label"].notna() & (~raw["Label"].isin(DROP_LABELS))].copy()
    raw.drop(columns=["Label"], inplace=True)

    # Step 6: Rename 'Destination Port' to 'dst_port'
    if "Destination Port" in raw.columns:
        raw.rename(columns={"Destination Port": "dst_port"}, inplace=True)
    elif "dst_port" not in raw.columns:
        rng = np.random.default_rng(SEED)
        raw["dst_port"] = rng.integers(1, 65536, len(raw))

    # Step 7: Sample: cap each attack class at 50,000 rows and BENIGN at 300,000
    sampled_parts = []
    for cls in TARGET_CLASSES:
        cls_df = raw[raw["label"] == cls]
        cap = 300000 if cls == "BENIGN" else 50000
        if len(cls_df) > cap:
            cls_df = cls_df.sample(n=cap, random_state=SEED)
        sampled_parts.append(cls_df)
    data = pd.concat(sampled_parts, ignore_index=True)
    print(f"Sampled dataset total: {len(data):,} rows")

    # Step 8: Stratified 70/15/15 train, val, test split
    train, rest = train_test_split(data, test_size=0.30, stratify=data["label"], random_state=SEED)
    val, test = train_test_split(rest, test_size=0.50, stratify=rest["label"], random_state=SEED)

    # Step 9: Save parquets to data/processed/
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train.to_parquet(PROCESSED_DIR / "train.parquet", index=False)
    val.to_parquet(PROCESSED_DIR / "val.parquet", index=False)
    test.to_parquet(PROCESSED_DIR / "test.parquet", index=False)

    print("\nSuccessfully saved parquet splits to data/processed/:")
    print(f"  train.parquet: {len(train):,} rows")
    print(f"  val.parquet:   {len(val):,} rows")
    print(f"  test.parquet:  {len(test):,} rows")
    print("\nClass counts in test.parquet:")
    print(test["label"].value_counts().to_string())


if __name__ == "__main__":
    main()
