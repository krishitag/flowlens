"""Run the full pipeline (M2.6): replay -> tier-1 monitor -> tier-2 detect -> explain -> SQLite.

    python -m pipeline.run --scenario scenarios/demo.json --speed 1 [--db data/events.db] [--explain-cap 300]

At most `explain_cap` flagged flows are explained per window, so a heavy window still fits the 1 s budget.
The rest are still stored as alerts, with no top features and NOT_EXPLAINED as the explanation.
"""
import argparse
import math
import time
from pathlib import Path

import numpy as np

from pipeline.detector import Detector
from pipeline.explainer import Explainer
from pipeline.monitor import Monitor
from pipeline.replayer import replay
from pipeline.store import Store

PACKET_COLS = ["Total Fwd Packets", "Total Backward Packets"]
BYTE_COLS = ["Total Length of Fwd Packets", "Total Length of Bwd Packets"]
EXPLAIN_CAP = 300
NOT_EXPLAINED = "Not explained: per-window explanation budget reached"


def column_sum(df, cols):
    """Sum of `cols` over the window, or 0 if the features aren't in test.parquet."""
    if not all(c in df.columns for c in cols):
        return 0
    return int(df[cols].to_numpy().sum())


def percentile(values, q):
    return float(np.percentile(values, q)) if values else None


def pick_to_explain(flagged, cap):
    """Boolean mask over `flagged`: the `cap` most confident flows.

    LightGBM-flagged flows ('lgbm' / 'both') come first, highest pred_prob first;
    then IForest-only flows, lowest (most anomalous) if_score first.
    """
    iforest_only = (flagged["source"] == "iforest").to_numpy()
    key = np.where(iforest_only, flagged["if_score"].to_numpy(dtype=float), -flagged["pred_prob"].to_numpy(dtype=float))
    order = np.lexsort((key, iforest_only))  # last key sorts first: LightGBM-flagged before IForest-only
    mask = np.zeros(len(flagged), dtype=bool)
    mask[order[:cap]] = True
    return mask


def run_pipeline(scenario, speed=1.0, db="data/events.db", verbose=True, explain_cap=EXPLAIN_CAP):
    """Run a scenario end to end into `db` (deleted first).

    Returns one stats dict per window: ts, state, flows, scored, explained,
    detect_ms and explain_ms (per explained flow, this window) and e2e_ms (whole window).
    """
    # fresh DB every run (including WAL side files)
    for suffix in ["", "-wal", "-shm"]:
        Path(str(db) + suffix).unlink(missing_ok=True)

    store = Store(db)
    monitor = Monitor()
    detector = Detector()
    explainer = Explainer()

    stats = []
    detect_ms, explain_ms = [], []
    total_alerts = 0

    for ts, window in replay(scenario, speed=speed):
        start = time.perf_counter()
        z, state = monitor.update(len(window))
        flagged, scored = detector.detect(window, state)

        chosen = pick_to_explain(flagged, explain_cap)
        picked = flagged[chosen]
        explained_iter = iter(explainer.explain(picked, picked["pred_label"], picked["source"]))
        explained = [next(explained_iter) if c else ("[]", NOT_EXPLAINED, 0.0) for c in chosen]
        n_explained = int(chosen.sum())

        alerts = []
        for row, (top_features, explanation, e_ms) in zip(flagged.to_dict("records"), explained):
            if_score = row["if_score"]
            alerts.append({
                "ts": float(ts),
                "flow_idx": int(row["flow_idx"]),
                "dst_port": int(row["dst_port"]),
                "true_label": row["label"],
                "pred_label": row["pred_label"],
                "pred_prob": float(row["pred_prob"]),
                "if_score": None if math.isnan(if_score) else float(if_score),
                "source": row["source"],
                "top_features": top_features,
                "explanation": explanation,
                "detect_ms": float(row["detect_ms"]),
                "explain_ms": float(e_ms),
            })

        store.insert_window({
            "ts": float(ts),
            "flows": len(window),
            "packets": column_sum(window, PACKET_COLS),
            "bytes": column_sum(window, BYTE_COLS),
            "z_score": float(z),
            "state": state,
            "scored": scored,
            "explained": n_explained,
        })
        store.insert_alerts(alerts)

        stats.append({
            "ts": float(ts),
            "state": state,
            "flows": len(window),
            "scored": scored,
            "explained": n_explained,
            "detect_ms": detector.last_detect_ms,
            "explain_ms": explained[np.argmax(chosen)][2] if n_explained else 0.0,
            "e2e_ms": (time.perf_counter() - start) * 1000,
        })
        total_alerts += len(alerts)
        detect_ms += [a["detect_ms"] for a in alerts]
        explain_ms += [e[2] for e, c in zip(explained, chosen) if c]
        if verbose:
            print(f"ts={ts:>5.0f}  {state:<8}  z={z:>7.2f}  flows={len(window):>4}  scored={scored:>4}  "
                  f"alerts={len(alerts):>4}  explained={n_explained:>4}")

    # detect percentiles are over all alerts; explain percentiles only over alerts that were explained
    meta = {
        "scenario": str(scenario),
        "speed": speed,
        "explain_cap": explain_cap,
        "total_flows": sum(s["flows"] for s in stats),
        "total_alerts": total_alerts,
        "total_explained": len(explain_ms),
        "detect_ms_p50": percentile(detect_ms, 50),
        "detect_ms_p95": percentile(detect_ms, 95),
        "explain_ms_p50": percentile(explain_ms, 50),
        "explain_ms_p95": percentile(explain_ms, 95),
    }
    for key, value in meta.items():
        store.set_meta(key, value)
    store.close()
    if verbose:
        print(meta)
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--db", default="data/events.db")
    parser.add_argument("--explain-cap", type=int, default=EXPLAIN_CAP, help="max flows explained per window")
    args = parser.parse_args()
    run_pipeline(args.scenario, args.speed, args.db, explain_cap=args.explain_cap)


if __name__ == "__main__":
    main()
