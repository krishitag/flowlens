"""M1.8: per-flow explanation latency, TreeSHAP vs Kernel SHAP, on the final LightGBM model.

Usage: python ml/benchmark_explain.py
- Flows: test flows flagged by the pipeline's rule (LightGBM non-BENIGN with prob >= 0.5, or IForest past threshold).
- TreeSHAP: 200 flows, explainer built once (not timed), one flow per call.
- Kernel SHAP: first 50 of those flows, background = 100 BENIGN train flows, default nsamples, one flow per call.
- Both explain the same output: LightGBM's raw per-class scores.
- Kernel SHAP's time varies from run to run, so it is timed in ROUNDS rounds and the speed-up is reported as a range.
This is the only file in the repo allowed to use KernelExplainer.
Writes reports/explain_benchmark.json and reports/figures/shap_latency.png.
"""
import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

SEED = 0
N_TREE = 200
N_KERNEL = 50
N_BACKGROUND = 100
ROUNDS = 3


def time_per_flow(explain, X):
    times = []
    for i in range(len(X)):
        start = time.perf_counter()
        explain(X[i:i + 1])
        times.append((time.perf_counter() - start) * 1000)
    return {
        "mean_ms": float(np.mean(times)),
        "p50_ms": float(np.percentile(times, 50)),
        "p95_ms": float(np.percentile(times, 95)),
        "n_flows": len(times),
    }


def main():
    features = json.loads((MODELS_DIR / "features.json").read_text())
    lgbm = joblib.load(MODELS_DIR / "lgbm.joblib")
    iforest = joblib.load(MODELS_DIR / "iforest.joblib")
    threshold = json.loads((MODELS_DIR / "iforest_threshold.json").read_text())["threshold"]
    test = pd.read_parquet(DATA_DIR / "test.parquet")
    train = pd.read_parquet(DATA_DIR / "train.parquet")

    # Same flag rule as the pipeline
    proba = lgbm.predict_proba(test[features])
    flagged = ((proba.argmax(axis=1) != 0) & (proba.max(axis=1) >= 0.5)) | (
        iforest.score_samples(test[features]) < threshold
    )
    flows = test.loc[flagged, features].sample(n=N_TREE, random_state=SEED).to_numpy(dtype=float)
    background = train.loc[train["label"] == "BENIGN", features].sample(n=N_BACKGROUND, random_state=SEED)
    print(f"{flagged.sum():,} flagged test flows, benchmarking on {N_TREE} (TreeSHAP) and {N_KERNEL} (Kernel SHAP)")

    tree_explainer = shap.TreeExplainer(lgbm)
    tree = time_per_flow(tree_explainer.shap_values, flows)
    print(f"TreeSHAP:    p50 {tree['p50_ms']:.3f} ms, p95 {tree['p95_ms']:.3f} ms, mean {tree['mean_ms']:.3f} ms")

    raw_scores = lambda X: lgbm.booster_.predict(X, raw_score=True)
    kernel_explainer = shap.KernelExplainer(raw_scores, background.to_numpy(dtype=float))
    rounds = []
    for r in range(ROUNDS):
        rounds.append(time_per_flow(lambda x: kernel_explainer.shap_values(x, silent=True), flows[:N_KERNEL]))
        print(f"Kernel SHAP round {r + 1}: p50 {rounds[-1]['p50_ms']:.1f} ms, p95 {rounds[-1]['p95_ms']:.1f} ms")
    kernel = {key: float(np.median([k[key] for k in rounds])) for key in ("mean_ms", "p50_ms", "p95_ms")}
    kernel.update(n_flows=N_KERNEL, rounds=ROUNDS)

    speedups = [k["p50_ms"] / tree["p50_ms"] for k in rounds]
    low, high = min(speedups), max(speedups)
    print(f"TreeSHAP is ~{low:,.0f}-{high:,.0f}x faster at the median")

    results = {
        "tree_shap": tree,
        "kernel_shap": kernel,
        "speedup_p50_range": [low, high],
        "speedup_note": f"~{low:,.0f}-{high:,.0f}x at the median, across {ROUNDS} Kernel SHAP rounds",
        "kernel_background": N_BACKGROUND,
        "flagged_test_flows": int(flagged.sum()),
    }
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "explain_benchmark.json").write_text(json.dumps(results, indent=2))

    fig, ax = plt.subplots(figsize=(7, 3))
    names = ["TreeSHAP", "Kernel SHAP"]
    p50 = [tree["p50_ms"], kernel["p50_ms"]]
    p95 = [tree["p95_ms"], kernel["p95_ms"]]
    ax.barh(names, p95, color="#cccccc", label="p95")
    ax.barh(names, p50, color=["#2b6cb0", "#c53030"], label="p50")
    for i, (a, b) in enumerate(zip(p50, p95)):
        ax.text(b * 1.15, i, f"p50 {a:,.2f} ms · p95 {b:,.2f} ms", va="center", fontsize=9)
    ax.set_xscale("log")
    ax.set_xlim(right=max(p95) * 100)
    ax.set_xlabel("Explanation time per flow (ms, log scale)")
    ax.set_title(f"TreeSHAP vs Kernel SHAP: ~{low:,.0f}-{high:,.0f}x faster at the median")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "shap_latency.png", dpi=150)
    plt.close(fig)
    print("\nwrote reports/explain_benchmark.json, reports/figures/shap_latency.png")


if __name__ == "__main__":
    main()
