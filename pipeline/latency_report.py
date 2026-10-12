"""Latency report (M2.8): run a scenario at speed 0 into a temporary DB and write reports/pipeline_latency.json.

    python -m pipeline.latency_report --scenario scenarios/stress.json

- detect_ms: over every scored flow (each flow gets its window's batch time / batch size).
- explain_ms: over every explained flow (only flagged flows are explained).
- e2e_ms: per window, from receiving the window to finishing the DB writes.
"""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np

from pipeline.run import run_pipeline

OUT = Path(__file__).resolve().parent.parent / "reports" / "pipeline_latency.json"


def summary(values):
    if len(values) == 0:
        return {"p50": None, "p95": None, "mean": None, "n": 0}
    return {
        "p50": round(float(np.percentile(values, 50)), 4),
        "p95": round(float(np.percentile(values, 95)), 4),
        "mean": round(float(np.mean(values)), 4),
        "n": int(len(values)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        stats = run_pipeline(args.scenario, speed=0, db=Path(tmp) / "events.db", verbose=False)

    detect = np.repeat([s["detect_ms"] for s in stats], [s["scored"] for s in stats])
    explain = np.repeat([s["explain_ms"] for s in stats], [s["explained"] for s in stats])
    e2e = [s["e2e_ms"] for s in stats]

    by_state = {}
    for state in ["NORMAL", "ELEVATED"]:
        rows = [s for s in stats if s["state"] == state]
        flows = sum(s["flows"] for s in rows)
        scored = sum(s["scored"] for s in rows)
        explained = sum(s["explained"] for s in rows)
        by_state[state] = {
            "windows": len(rows),
            "flows": flows,
            "scored": scored,
            "explained": explained,
            "pct_scored": round(100 * scored / flows, 2) if flows else None,
            "pct_explained": round(100 * explained / flows, 2) if flows else None,
        }

    report = {
        "scenario": args.scenario,
        "windows": len(stats),
        "total_flows": int(sum(s["flows"] for s in stats)),
        "detect_ms": summary(detect),
        "explain_ms": summary(explain),
        "e2e_ms_per_window": summary(e2e),
        "by_state": by_state,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"wrote {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
