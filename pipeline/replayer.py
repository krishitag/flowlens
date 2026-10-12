"""Replayer (M2.2): turns a scenario JSON (contract 4.4) into a stream of windows of test.parquet flows.

    python -m pipeline.replayer
"""
import json
import time

import numpy as np
import pandas as pd


def replay(scenario_path, test_path="data/processed/test.parquet", speed=1.0, seed=0):
    """Yield (ts, window_df) once per window.

    Each window of a segment has rate * window_s flows: (1 - benign_mix) from the
    segment's label and the rest from BENIGN, sampled with replacement.
    window_df has every test.parquet column plus flow_idx (row index in test.parquet).
    ts = simulated seconds since start. speed 1 = real time, N = N times faster, 0 = no sleeping.
    """
    with open(scenario_path) as f:
        scenario = json.load(f)
    window_s = scenario["window_s"]

    test = pd.read_parquet(test_path).reset_index(drop=True)
    rows_by_label = {label: idx.to_numpy() for label, idx in test.groupby("label").groups.items()}
    rng = np.random.default_rng(seed)

    start = time.perf_counter()
    window = 0
    for seg in scenario["segments"]:
        label = seg["label"]
        if label not in rows_by_label or "BENIGN" not in rows_by_label:
            raise ValueError(f"test.parquet has no rows for {label!r} or BENIGN")
        n_flows = round(seg["rate"] * window_s)
        n_label = round(n_flows * (1 - seg.get("benign_mix", 0)))

        for _ in range(round(seg["duration"] / window_s)):
            idx = np.concatenate([
                rng.choice(rows_by_label[label], n_label),
                rng.choice(rows_by_label["BENIGN"], n_flows - n_label),
            ])
            idx = rng.permutation(idx)
            window_df = test.iloc[idx].reset_index(drop=True)
            window_df["flow_idx"] = idx

            yield window * window_s, window_df

            window += 1
            if speed > 0:
                # pace against the wall clock so processing time doesn't add up
                wait = start + window * window_s / speed - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)


if __name__ == "__main__":
    for i, (ts, df) in enumerate(replay("scenarios/demo.json", speed=0)):
        if i == 5:
            break
        print(f"ts={ts:>3}  flows={len(df):>3}  {df['label'].value_counts().to_dict()}")

    # also show the first DoS windows (segment 2 starts at ts=30)
    for ts, df in replay("scenarios/demo.json", speed=0):
        if 30 <= ts < 32:
            print(f"ts={ts:>3}  flows={len(df):>3}  {df['label'].value_counts().to_dict()}")
        elif ts >= 32:
            break
