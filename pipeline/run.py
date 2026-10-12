"""Run the full pipeline (M2.6): replay -> tier-1 monitor -> tier-2 detect -> explain -> SQLite.

    python -m pipeline.run --scenario scenarios/demo.json --speed 1 [--db data/events.db]
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


def column_sum(df, cols):
    """Sum of `cols` over the window, or 0 if the features aren't in test.parquet."""
    if not all(c in df.columns for c in cols):
        return 0
    return int(df[cols].to_numpy().sum())


def percentile(values, q):
    return float(np.percentile(values, q)) if values else None


def run_pipeline(scenario, speed=1.0, db="data/events.db", verbose=True):
    """Run a scenario end to end into `db` (deleted first).

    Returns one stats dict per window: ts, state, flows, scored, explained,
    detect_ms and explain_ms (per flow, this window) and e2e_ms (whole window).
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

    for ts, window in replay(scenario, speed=speed):
        start = time.perf_counter()
        z, state = monitor.update(len(window))
        flagged, scored = detector.detect(window, state)
        explained = explainer.explain(flagged, flagged["pred_label"], flagged["source"])

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
            "explained": len(alerts),
        })
        store.insert_alerts(alerts)

        stats.append({
            "ts": float(ts),
            "state": state,
            "flows": len(window),
            "scored": scored,
            "explained": len(alerts),
            "detect_ms": detector.last_detect_ms,
            "explain_ms": alerts[0]["explain_ms"] if alerts else 0.0,
            "e2e_ms": (time.perf_counter() - start) * 1000,
        })
        detect_ms += [a["detect_ms"] for a in alerts]
        explain_ms += [a["explain_ms"] for a in alerts]
        if verbose:
            print(f"ts={ts:>5.0f}  {state:<8}  z={z:>7.2f}  flows={len(window):>4}  scored={scored:>4}  alerts={len(alerts):>4}")

    # latency percentiles are over alerted flows (the ones that were both scored and explained)
    meta = {
        "scenario": str(scenario),
        "speed": speed,
        "total_flows": sum(s["flows"] for s in stats),
        "total_alerts": len(explain_ms),
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
    args = parser.parse_args()
    run_pipeline(args.scenario, args.speed, args.db)


if __name__ == "__main__":
    main()
