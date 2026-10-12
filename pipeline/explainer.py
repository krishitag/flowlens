"""Tier-2 explainer (M2.5): TreeSHAP contributions -> top 3 features -> readable sentences.

Both TreeExplainers are built once, when Explainer() is created.
Contributions are stored so that positive = pushes the flow toward "anomalous":
- LightGBM: SHAP values for the predicted class (raw log-odds).
- IsolationForest: SHAP values are in path-length space, where a shorter path
  means more anomalous, so they are negated.

Quick check (needs models/ and data/processed/test.parquet):
    python -m pipeline.explainer
"""
import json
import time
from pathlib import Path

import joblib
import numpy as np
import shap

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
TOP_K = 3


def percentile_of(value, quantiles):
    """Share of benign flows (0-100) with a value <= `value`, from the 101 benign percentiles."""
    return int(np.clip(np.searchsorted(quantiles, value, side="right") - 1, 0, 100))


def format_value(value):
    if float(value).is_integer() or abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def describe_feature(name, value, baseline):
    """One sentence, e.g. 'Flow Packets/s = 4,812 (above 99.9% of normal flows)'.

    baseline = [q0, q1, ..., q100, q99_9] from models/baselines.json.
    """
    q, q99_9 = baseline[:101], baseline[101]
    # left/right differ when benign percentiles tie (e.g. many zeros), so "above"
    # only counts strictly smaller percentiles and "below" strictly larger ones
    left = np.searchsorted(q, value, side="left")
    right = np.searchsorted(q, value, side="right")
    pct_below = max(left - 1, 0)
    pct_above = max(100 - right, 0)
    tied = right - left
    if value > q99_9:
        where = "above 99.9% of normal flows"
    elif value < q[0]:
        where = "below every normal flow"
    elif pct_below >= 90:
        where = f"above {min(pct_below, 99)}% of normal flows"
    elif pct_above >= 90:
        where = f"below {min(pct_above, 99)}% of normal flows"
    elif tied >= 20:
        where = f"same value as about {tied}% of normal flows"
    else:
        where = f"typical for normal flows, percentile {pct_below}"
    return f"{name} = {format_value(value)} ({where})"


class Explainer:
    def __init__(self, models_dir=MODELS_DIR):
        models_dir = Path(models_dir)
        self.features = json.loads((models_dir / "features.json").read_text())
        labels = json.loads((models_dir / "labels.json").read_text())
        baselines = json.loads((models_dir / "baselines.json").read_text())
        self.baselines = {f: np.asarray(baselines[f], dtype=float) for f in self.features}

        lgbm = joblib.load(models_dir / "lgbm.joblib")
        iforest = joblib.load(models_dir / "iforest.joblib")
        # SHAP output columns follow lgbm.classes_ (ids like 0..6, or names if trained on strings)
        self.class_col = {labels.get(str(c), str(c)): col for col, c in enumerate(lgbm.classes_)}

        self.lgbm_explainer = shap.TreeExplainer(lgbm)
        self.iforest_explainer = shap.TreeExplainer(iforest)

    def explain(self, flows, pred_labels, sources):
        """Explain flagged flows.

        flows: DataFrame of flagged flows (must contain the features.json columns).
        pred_labels: LightGBM predicted label per flow, e.g. "DoS".
        sources: 'lgbm' | 'iforest' | 'both' per flow. Only 'iforest' uses the IForest explainer.
        Returns a list of (top_features_json, explanation, explain_ms), one per flow, in order.
        explain_ms = batch time / number of flows.
        """
        n = len(flows)
        if n == 0:
            return []
        start = time.perf_counter()

        X = flows[self.features]
        sources = np.asarray(sources)
        pred_labels = np.asarray(pred_labels)
        contribs = np.zeros((n, len(self.features)))

        use_if = (sources == "iforest") | (pred_labels == "BENIGN")
        if (~use_if).any():
            cols = np.array([self.class_col[label] for label in pred_labels[~use_if]])
            vals = self._lgbm_shap(X[~use_if])
            contribs[~use_if] = vals[np.arange(len(cols)), :, cols]
        if use_if.any():
            contribs[use_if] = -self.iforest_explainer.shap_values(X[use_if])

        values = X.to_numpy(dtype=float)
        results = [self._describe(values[i], contribs[i]) for i in range(n)]
        ms = (time.perf_counter() - start) * 1000 / n
        return [(top, text, ms) for top, text in results]

    def _lgbm_shap(self, X):
        """SHAP values as (flows, features, classes)."""
        vals = self.lgbm_explainer.shap_values(X)
        if isinstance(vals, list):  # older shap returns one array per class
            vals = np.stack(vals, axis=-1)
        return vals

    def _describe(self, row, contrib):
        top = [i for i in np.argsort(contrib)[::-1][:TOP_K] if contrib[i] > 0]
        top_features, sentences = [], []
        for i in top:
            name, value = self.features[i], float(row[i])
            baseline = self.baselines[name]
            top_features.append({
                "name": name,
                "value": value,
                "contribution": round(float(contrib[i]), 4),
                "percentile": percentile_of(value, baseline[:101]),
            })
            sentences.append(describe_feature(name, value, baseline))
        if not sentences:
            sentences = ["No single feature stands out; flagged on the combined pattern."]
        return json.dumps(top_features), "\n".join(sentences)


if __name__ == "__main__":
    import pandas as pd

    explainer = Explainer()
    test = pd.read_parquet(ROOT / "data" / "processed" / "test.parquet")

    # IForest sign check: raw SHAP row sums should rise with score_samples (higher = more normal)
    iforest = joblib.load(MODELS_DIR / "iforest.joblib")
    check = test[explainer.features].sample(500, random_state=0)
    raw_sums = explainer.iforest_explainer.shap_values(check).sum(axis=1)
    corr = np.corrcoef(raw_sums, iforest.score_samples(check))[0, 1]
    print(f"IForest SHAP sum vs score_samples correlation: {corr:.3f} (should be strongly positive)")
    sample = test[test["label"] != "BENIGN"].groupby("label").head(1)

    lgbm = joblib.load(MODELS_DIR / "lgbm.joblib")
    cols = lgbm.predict_proba(sample[explainer.features]).argmax(axis=1)
    col_to_label = {col: label for label, col in explainer.class_col.items()}
    preds = [col_to_label[c] for c in cols]

    for source in ["lgbm", "iforest"]:
        print(f"\n=== explained with {source} ===")
        results = explainer.explain(sample, preds, [source] * len(sample))
        for true, pred, (top, text, ms) in zip(sample["label"], preds, results):
            print(f"\ntrue={true} pred={pred} explain_ms={ms:.2f}")
            print(text)
