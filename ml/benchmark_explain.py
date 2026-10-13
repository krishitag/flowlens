"""SHAP latency benchmark script (M1.8) for FlowLens.

Measures TreeSHAP vs. KernelSHAP per-flow explanation latency.
TreeSHAP is benchmarked on 200 flagged flows.
KernelSHAP is benchmarked on 50 flagged flows with 100 benign background samples.
Outputs:
  - reports/explain_benchmark.json
  - reports/figures/shap_latency.png

Usage:
    python ml/benchmark_explain.py
"""
import json
import time
from pathlib import Path
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SEED = 42


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    test = pd.read_parquet(PROCESSED_DIR / "test.parquet")
    train = pd.read_parquet(PROCESSED_DIR / "train.parquet")
    features = json.loads((MODELS_DIR / "features.json").read_text())
    lgbm = joblib.load(MODELS_DIR / "lgbm.joblib")

    # Select flagged attack flows for explanation benchmarking
    flagged_test = test[test["label"] != "BENIGN"].reset_index(drop=True)
    if len(flagged_test) < 200:
        flagged_test = test.reset_index(drop=True)

    # 1. TreeSHAP benchmark (200 flows)
    print("Benchmarking TreeSHAP on 200 flows...")
    tree_samples = flagged_test.iloc[:200][features]
    tree_explainer = shap.TreeExplainer(lgbm)

    tree_times_ms = []
    for i in range(len(tree_samples)):
        row = tree_samples.iloc[[i]]
        start = time.perf_counter()
        _ = tree_explainer.shap_values(row)
        tree_times_ms.append((time.perf_counter() - start) * 1000)

    tree_times_ms = np.array(tree_times_ms)
    tree_stats = {
        "mean_ms": float(np.mean(tree_times_ms)),
        "p50_ms": float(np.percentile(tree_times_ms, 50)),
        "p95_ms": float(np.percentile(tree_times_ms, 95)),
        "n_flows": len(tree_times_ms),
    }
    print(f"TreeSHAP: Mean={tree_stats['mean_ms']:.3f} ms, p50={tree_stats['p50_ms']:.3f} ms, p95={tree_stats['p95_ms']:.3f} ms")

    # 2. KernelSHAP benchmark (50 flows, 100 benign background samples)
    print("\nBenchmarking KernelSHAP on 50 flows (100 background samples)...")
    benign_train = train[train["label"] == "BENIGN"][features]
    bg_samples = benign_train.sample(n=min(100, len(benign_train)), random_state=SEED)
    kernel_samples = flagged_test.iloc[:50][features]

    # Predict function returning proba for the predicted class
    def predict_fn(X):
        return lgbm.predict_proba(X)

    kernel_explainer = shap.KernelExplainer(predict_fn, bg_samples, link="identity")

    kernel_times_ms = []
    for i in range(len(kernel_samples)):
        row = kernel_samples.iloc[[i]]
        start = time.perf_counter()
        _ = kernel_explainer.shap_values(row, nsamples=100, silent=True)
        kernel_times_ms.append((time.perf_counter() - start) * 1000)

    kernel_times_ms = np.array(kernel_times_ms)
    kernel_stats = {
        "mean_ms": float(np.mean(kernel_times_ms)),
        "p50_ms": float(np.percentile(kernel_times_ms, 50)),
        "p95_ms": float(np.percentile(kernel_times_ms, 95)),
        "n_flows": len(kernel_times_ms),
    }
    print(f"KernelSHAP: Mean={kernel_stats['mean_ms']:.1f} ms, p50={kernel_stats['p50_ms']:.1f} ms, p95={kernel_stats['p95_ms']:.1f} ms")

    speedup = kernel_stats["p50_ms"] / max(tree_stats["p50_ms"], 1e-6)
    print(f"\nTreeSHAP speed-up over KernelSHAP: {speedup:,.0f}x")

    # Save benchmark JSON
    benchmark_data = {
        "tree_shap": tree_stats,
        "kernel_shap": kernel_stats,
    }
    out_json = REPORTS_DIR / "explain_benchmark.json"
    out_json.write_text(json.dumps(benchmark_data, indent=2))
    print(f"Saved {out_json}")

    # Plot comparison figure
    fig, ax = plt.subplots(figsize=(7, 4), facecolor="#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    methods = ["Kernel SHAP", "TreeSHAP"]
    medians = [kernel_stats["p50_ms"], tree_stats["p50_ms"]]
    colors = ["#ef4444", "#3b82f6"]

    bars = ax.barh(methods, medians, color=colors, height=0.5)
    ax.set_xscale("log")
    ax.set_xlabel("Latency per flow, median (ms, log scale)", color="#f0f0f0")
    ax.set_title(f"Explanation Latency: TreeSHAP vs Kernel SHAP ({speedup:,.0f}x Speed-up)", color="#f0f0f0")
    ax.tick_params(colors="#d0d0d0")
    ax.grid(axis="x", linestyle="--", alpha=0.3)

    for bar in bars:
        w = bar.get_width()
        ax.text(w * 1.3, bar.get_y() + bar.get_height() / 2, f"{w:,.2f} ms",
                va="center", color="#f0f0f0", fontweight="bold")

    fig.tight_layout()
    fig_path = FIGURES_DIR / "shap_latency.png"
    fig.savefig(fig_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    print(f"Saved figure to {fig_path}")


if __name__ == "__main__":
    main()
