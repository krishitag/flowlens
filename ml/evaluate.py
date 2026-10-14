"""M1.6: evaluate LightGBM and the RF baseline on the test split.

Usage: python ml/evaluate.py
Writes reports/results.json, reports/figures/confusion_lgbm.png and reports/figures/per_class_f1.png.
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
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

SEED = 0
N_SINGLE = 500  # flows timed one at a time


def latency(model, X):
    """Per-flow inference time in ms: batch time / batch size, and one-flow-at-a-time p50/p95."""
    start = time.perf_counter()
    model.predict_proba(X)
    batch_ms = (time.perf_counter() - start) * 1000 / len(X)

    rows = X.sample(n=N_SINGLE, random_state=SEED)
    single = []
    for i in range(len(rows)):
        start = time.perf_counter()
        model.predict_proba(rows.iloc[[i]])
        single.append((time.perf_counter() - start) * 1000)
    return {
        "latency_ms_per_flow_batch": batch_ms,
        "latency_ms_single_p50": float(np.percentile(single, 50)),
        "latency_ms_single_p95": float(np.percentile(single, 95)),
    }


def evaluate(model, X, y, classes):
    pred = model.predict(X)
    precision, recall, f1, support = precision_recall_fscore_support(
        y, pred, labels=range(len(classes)), zero_division=0
    )
    return {
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "benign_fpr": float((pred[y == 0] != 0).mean()),
        **latency(model, X),
        "classes": {
            c: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]), "support": int(support[i])}
            for i, c in enumerate(classes)
        },
        "confusion_matrix": confusion_matrix(y, pred, labels=range(len(classes))).tolist(),
    }


def plot_confusion(cm, classes, path):
    cm = np.array(cm)
    norm = cm / cm.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(classes)):
        for j in range(len(classes)):
            ax.text(j, i, f"{cm[i, j]:,}", ha="center", va="center", fontsize=8,
                    color="white" if norm[i, j] > 0.5 else "black")
    ax.set_xticks(range(len(classes)), classes, rotation=45, ha="right")
    ax.set_yticks(range(len(classes)), classes)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("LightGBM confusion matrix (test, colour = row-normalised)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_per_class_f1(results, classes, path):
    x = np.arange(len(classes))
    fig, ax = plt.subplots(figsize=(8, 4))
    for offset, (key, name) in zip((-0.2, 0.2), (("lgbm", "LightGBM"), ("rf", "Random Forest"))):
        ax.bar(x + offset, [results[key]["classes"][c]["f1"] for c in classes], width=0.4, label=name)
    ax.set_xticks(x, classes, rotation=30, ha="right")
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("F1 (test)")
    ax.set_title("Per-class F1")
    ax.legend(loc="upper center", ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    features = json.loads((MODELS_DIR / "features.json").read_text())
    labels = json.loads((MODELS_DIR / "labels.json").read_text())
    classes = [labels[str(i)] for i in range(len(labels))]

    test = pd.read_parquet(DATA_DIR / "test.parquet")
    X = test[features]
    y = test["label"].map({c: i for i, c in enumerate(classes)}).to_numpy()

    results = {}
    for key in ("lgbm", "rf"):
        results[key] = evaluate(joblib.load(MODELS_DIR / f"{key}.joblib"), X, y, classes)
        r = results[key]
        print(f"{key}: macro F1 {r['macro_f1']:.4f}, benign FPR {r['benign_fpr']:.4f}, "
              f"{r['latency_ms_per_flow_batch']:.4f} ms/flow batched, {r['latency_ms_single_p50']:.3f} ms single-flow p50")
        for c in classes:
            print(f"    {c:<11} F1 {r['classes'][c]['f1']:.4f}")

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "results.json").write_text(json.dumps(results, indent=2))
    plot_confusion(results["lgbm"]["confusion_matrix"], classes, FIGURES_DIR / "confusion_lgbm.png")
    plot_per_class_f1(results, classes, FIGURES_DIR / "per_class_f1.png")
    print("\nwrote reports/results.json, reports/figures/confusion_lgbm.png, reports/figures/per_class_f1.png")


if __name__ == "__main__":
    main()
