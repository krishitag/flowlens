"""Model evaluation script (M1.6) for FlowLens.

Evaluates LightGBM and RandomForest on the test split.
Generates macro/per-class F1, precision, recall, benign FPR, confusion matrix,
and per-flow inference latency.
Outputs:
  - reports/results.json
  - reports/figures/confusion_lgbm.png
  - reports/figures/per_class_f1.png

Usage:
    python ml/evaluate.py
"""
import json
import time
from pathlib import Path
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
SEED = 42

CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
LABEL_TO_ID = {c: i for i, c in enumerate(CLASSES)}


def evaluate_model(model, X, y, class_names):
    """Computes full classification metrics, latency, and benign FPR."""
    n = len(X)

    # Time batch inference to calculate per-flow latency (ms)
    start = time.perf_counter()
    y_pred = model.predict(X)
    latency_ms = (time.perf_counter() - start) * 1000 / n

    macro_f1 = float(f1_score(y, y_pred, average="macro"))

    # Benign False Positive Rate: benign flows (y == 0) predicted as attacks (y_pred != 0)
    benign_mask = (y == 0)
    benign_count = int(np.sum(benign_mask))
    benign_fp = int(np.sum((y_pred != 0) & benign_mask))
    benign_fpr = float(benign_fp / benign_count) if benign_count > 0 else 0.0

    # Per-class metrics
    report = classification_report(y, y_pred, target_names=class_names, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, y_pred, labels=range(len(class_names)))

    classes_dict = {}
    for c in class_names:
        c_metrics = report.get(c, {})
        classes_dict[c] = {
            "f1": float(c_metrics.get("f1-score", 0.0)),
            "precision": float(c_metrics.get("precision", 0.0)),
            "recall": float(c_metrics.get("recall", 0.0)),
            "support": int(c_metrics.get("support", 0)),
        }

    return {
        "macro_f1": macro_f1,
        "benign_fpr": benign_fpr,
        "latency_ms": latency_ms,
        "classes": classes_dict,
        "confusion_matrix": cm.tolist(),
        "y_pred": y_pred,
    }


def plot_confusion_matrix(cm, classes, out_path):
    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    ax.figure.colorbar(im, ax=ax)

    ax.set(
        xticks=np.arange(cm.shape[1]),
        yticks=np.arange(cm.shape[0]),
        xticklabels=classes,
        yticklabels=classes,
        title="LightGBM Confusion Matrix",
        ylabel="True label",
        xlabel="Predicted label",
    )
    ax.title.set_color("#f0f0f0")
    ax.yaxis.label.set_color("#f0f0f0")
    ax.xaxis.label.set_color("#f0f0f0")
    ax.tick_params(colors="#d0d0d0")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j, i, f"{cm[i, j]:,}",
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "#d0d0d0",
                fontsize=8,
            )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)


def plot_per_class_f1(results, classes, out_path):
    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#1e1e1e")
    ax.set_facecolor("#1e1e1e")
    x = np.arange(len(classes))
    width = 0.35

    lgbm_f1 = [results["lgbm"]["classes"][c]["f1"] for c in classes]
    rf_f1 = [results["rf"]["classes"][c]["f1"] for c in classes]

    rects1 = ax.bar(x - width / 2, lgbm_f1, width, label="LightGBM", color="#3b82f6")
    rects2 = ax.bar(x + width / 2, rf_f1, width, label="Random Forest", color="#10b981")

    ax.set_ylabel("F1 Score", color="#f0f0f0")
    ax.set_title("Per-Class F1 Score Comparison", color="#f0f0f0")
    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=30, ha="right", color="#d0d0d0")
    ax.set_ylim([0, 1.05])
    ax.tick_params(colors="#d0d0d0")
    ax.legend(facecolor="#2a2a2a", edgecolor="#444", labelcolor="#f0f0f0")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    test_path = PROCESSED_DIR / "test.parquet"
    if not test_path.exists():
        raise FileNotFoundError(f"{test_path} missing. Run ml/prepare.py first.")

    features = json.loads((MODELS_DIR / "features.json").read_text())
    lgbm = joblib.load(MODELS_DIR / "lgbm.joblib")
    rf = joblib.load(MODELS_DIR / "rf.joblib")

    test = pd.read_parquet(test_path)
    test["y"] = test["label"].map(LABEL_TO_ID)
    X_test = test[features]
    y_test = test["y"]

    print("Evaluating LightGBM...")
    res_lgbm = evaluate_model(lgbm, X_test, y_test, CLASSES)

    print("Evaluating Random Forest...")
    res_rf = evaluate_model(rf, X_test, y_test, CLASSES)

    # Save reports/results.json
    results_json_data = {
        "lgbm": {
            "macro_f1": res_lgbm["macro_f1"],
            "benign_fpr": res_lgbm["benign_fpr"],
            "latency_ms": res_lgbm["latency_ms"],
            "classes": res_lgbm["classes"],
        },
        "rf": {
            "macro_f1": res_rf["macro_f1"],
            "benign_fpr": res_rf["benign_fpr"],
            "latency_ms": res_rf["latency_ms"],
            "classes": res_rf["classes"],
        },
    }
    (REPORTS_DIR / "results.json").write_text(json.dumps(results_json_data, indent=2))
    print(f"Saved {REPORTS_DIR / 'results.json'}")

    # Generate figures
    cm_lgbm = np.array(res_lgbm["confusion_matrix"])
    plot_confusion_matrix(cm_lgbm, CLASSES, FIGURES_DIR / "confusion_lgbm.png")
    plot_per_class_f1(results_json_data, CLASSES, FIGURES_DIR / "per_class_f1.png")
    print(f"Saved figures to {FIGURES_DIR}")

    print("\n--- Summary Results ---")
    print(f"LightGBM Macro F1: {res_lgbm['macro_f1']:.3f} | Benign FPR: {res_lgbm['benign_fpr']:.2%} | Latency: {res_lgbm['latency_ms']:.4f} ms/flow")
    print(f"RF Macro F1:       {res_rf['macro_f1']:.3f} | Benign FPR: {res_rf['benign_fpr']:.2%} | Latency: {res_rf['latency_ms']:.4f} ms/flow")


if __name__ == "__main__":
    main()
