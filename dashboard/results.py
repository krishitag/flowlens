"""Results tab (M3.5): reports/*.json and reports/figures/*.png.

Member 1's JSON layouts aren't frozen, so the parsers look for structure instead of exact keys:
- results.json: one dict per model (e.g. {"lgbm": {...}, "rf": {...}}) or a single flat model.
  Scalars become stat tiles; a dict keyed by class names becomes the per-class table.
- holdout.json: {held_out_class: {metric: value}} -> table.
- explain_benchmark.json: keys containing "tree" / "kernel", each with p50/p95/mean (ms).
- pipeline_latency.json: Member 2's format (pipeline/latency_report.py).
Anything unrecognised falls back to raw JSON, so a format change never crashes the tab.
"""
import json
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import ui

REPORTS = Path(__file__).resolve().parent.parent / "reports"
FIGURES = REPORTS / "figures"
CLASSES = ["BENIGN", "DoS", "DDoS", "PortScan", "BruteForce", "WebAttack", "Bot"]
MODEL_NAMES = {"lgbm": "LightGBM", "lightgbm": "LightGBM", "rf": "Random Forest", "random_forest": "Random Forest",
               "iforest": "Isolation Forest", "either": "Either"}


def load(name):
    path = REPORTS / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


TOKENS = {"lgbm": "LightGBM", "lightgbm": "LightGBM", "rf": "RF", "iforest": "IForest", "f1": "F1",
          "fpr": "FPR", "ms": "(ms)", "macro": "Macro", "n": "n"}


def nice(key):
    """'lgbm_recall' -> 'LightGBM recall', 'macro_f1' -> 'Macro F1'."""
    key = str(key)
    if key.lower() in MODEL_NAMES:
        return MODEL_NAMES[key.lower()]
    if key.lower() in ("n", "n_flows", "support"):
        return "Flows"
    words = [TOKENS.get(w.lower(), w) for w in key.replace("-", "_").split("_")]
    return " ".join(words)[:1].upper() + " ".join(words)[1:]


def fmt(v, pct=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if pct:
        return f"{100 * v:.1f}%"
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.3f}" if abs(v) < 100 else f"{v:,.1f}"


def is_rate(key, v):
    """Metrics in [0, 1] that read better as percentages (F1, recall, FPR, accuracy...)."""
    words = ("f1", "recall", "precision", "fpr", "accuracy", "rate")
    return isinstance(v, float) and 0 <= v <= 1 and any(w in str(key).lower() for w in words)


def scalars(d):
    return {k: v for k, v in d.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def class_dict(d):
    """The first dict (searched recursively) whose keys are mostly class names."""
    if not isinstance(d, dict):
        return None
    if sum(k in CLASSES for k in d) >= 3:
        return d
    for v in d.values():
        found = class_dict(v)
        if found:
            return found
    return None


def class_f1(d):
    cd = class_dict(d) or {}
    out = {}
    for cls, v in cd.items():
        if isinstance(v, dict):
            v = next((v[k] for k in v if str(k).lower() in ("f1", "f1-score", "f1_score")), None)
        if isinstance(v, (int, float)):
            out[cls] = v
    return out


def figure(name, caption):
    path = FIGURES / name
    if path.exists():
        st.image(str(path), caption=caption, width="stretch")


def missing(report, owner):
    ui.html(f'<div class="fl-card" style="color:{ui.MUTED};font-size:0.85rem">'
            f'<code>reports/{report}</code> isn\'t available yet ({owner}). '
            f'It will appear here once it\'s pushed. Use <b>Reload reports</b> above.</div>')


# ---------- sections ----------

def shap_benchmark():
    ui.section("TreeSHAP vs Kernel SHAP", "Headline result · per-flow explanation latency")
    data = load("explain_benchmark.json")
    if data is None:
        missing("explain_benchmark.json", "Member 1, M1.8")
        return

    methods = {}
    for key, v in (data.items() if isinstance(data, dict) else []):
        if isinstance(v, dict) and ("tree" in key.lower() or "kernel" in key.lower()):
            methods["TreeSHAP" if "tree" in key.lower() else "Kernel SHAP"] = scalars(v)
    if len(methods) < 2:
        st.json(data)
        return

    def stat(m, *names):
        return next((methods[m][k] for k in methods[m] if any(n == k.lower() for n in names)), None)

    tree_p50 = stat("TreeSHAP", "p50", "median", "p50_ms", "median_ms")
    kern_p50 = stat("Kernel SHAP", "p50", "median", "p50_ms", "median_ms")
    tree_p95, kern_p95 = stat("TreeSHAP", "p95", "p95_ms"), stat("Kernel SHAP", "p95", "p95_ms")
    tree_mean, kern_mean = stat("TreeSHAP", "mean", "mean_ms"), stat("Kernel SHAP", "mean", "mean_ms")
    base_t, base_k = tree_p50 or tree_mean, kern_p50 or kern_mean

    tiles = []
    if base_t and base_k:
        tiles.append(ui.tile("Speed-up (median)", f"{base_k / base_t:,.0f}×", "Kernel SHAP time ÷ TreeSHAP time"))
    tiles += [
        ui.tile("TreeSHAP p50 / p95", f"{fmt(tree_p50)} ms", f"p95 {fmt(tree_p95)} ms"),
        ui.tile("Kernel SHAP p50 / p95", f"{fmt(kern_p50)} ms", f"p95 {fmt(kern_p95)} ms"),
    ]
    ui.tiles(tiles)

    left, right = st.columns([3, 2])
    with left:
        names = ["Kernel SHAP", "TreeSHAP"]
        p50 = [kern_p50 or kern_mean, tree_p50 or tree_mean]
        fig = go.Figure(go.Bar(
            x=p50, y=names, orientation="h", marker=dict(color=ui.SERIES, cornerradius=4),
            text=[f"{fmt(v)} ms" for v in p50], textposition="outside", textfont=dict(color=ui.INK_2),
            hovertemplate="%{y}: %{x:.3f} ms per flow (median)<extra></extra>",
        ))
        ui.plot_layout(fig, 200, bargap=0.45)
        lo, hi = math.log10(min(p50)), math.log10(max(p50))
        fig.update_traces(cliponaxis=False)
        fig.update_xaxes(type="log", dtick=1, range=[math.floor(lo) - 0.3, hi + 1.0],
                         title=dict(text="ms per flow, median (log scale)", font=dict(color=ui.MUTED)))
        st.plotly_chart(fig, width="stretch")
    with right:
        rows = [[m, fmt(stat(m, "mean", "mean_ms")), fmt(stat(m, "p50", "median", "p50_ms")),
                 fmt(stat(m, "p95", "p95_ms")), fmt(stat(m, "n", "flows", "n_flows"))] for m in names]
        ui.html('<div class="fl-card">' + ui.table(rows, ["Method", "Mean", "p50", "p95", "Flows"]) + "</div>")
    figure("shap_latency.png", "Member 1's benchmark figure")


def classification():
    ui.section("Classification", "LightGBM vs Random Forest baseline · test split")
    data = load("results.json")
    if data is None:
        missing("results.json", "Member 1, M1.6")
        return
    if not isinstance(data, dict):
        st.json(data)
        return
    # top-level numbers = one flat model; otherwise one dict per model
    models = {"LightGBM": data} if scalars(data) else {k: v for k, v in data.items() if isinstance(v, dict)}

    tiles = []
    for name, d in models.items():
        for k, v in list(scalars(d).items())[:3]:
            tiles.append(ui.tile(f"{nice(name)} · {nice(k)}", fmt(v, is_rate(k, v))))
    if tiles:
        ui.tiles(tiles, cols=3)  # 3 metrics per model -> one row per model

    per_class = pd.DataFrame({nice(n): class_f1(d) for n, d in models.items()})
    if not per_class.empty:
        per_class = per_class.reindex([c for c in CLASSES if c in per_class.index])
        rows = [[cls] + [fmt(v, True) if pd.notna(v) else "–" for v in r] for cls, r in per_class.iterrows()]
        ui.html('<div class="fl-card">' + ui.table(rows, ["Class (F1)"] + list(per_class.columns)) + "</div>")
    elif not tiles:
        st.json(data)

    c1, c2 = st.columns(2)
    with c1:
        figure("confusion_lgbm.png", "Confusion matrix · LightGBM")
    with c2:
        figure("per_class_f1.png", "Per-class F1")


def holdout():
    ui.section("Leave-one-attack-out", "Recall on an attack class the classifier never saw")
    data = load("holdout.json")
    if data is None:
        missing("holdout.json", "Member 1, M1.7")
        return
    rows_src = {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}
    if not rows_src:
        st.json(data)
        return
    cols = list(dict.fromkeys(k for v in rows_src.values() for k in scalars(v)))
    rows = [[cls] + [fmt(v.get(c), is_rate(c, v.get(c))) if c in v else "–" for c in cols]
            for cls, v in rows_src.items()]
    ui.html('<div class="fl-card">' + ui.table(rows, ["Held-out class"] + [nice(c) for c in cols]) + "</div>")


def pipeline_latency():
    ui.section("Pipeline latency", "Member 2 · stress scenario replayed at full speed")
    lat = load("pipeline_latency.json")
    if lat is None:
        missing("pipeline_latency.json", "Member 2, M2.8")
        return
    d, e, w = lat.get("detect_ms", {}), lat.get("explain_ms", {}), lat.get("e2e_ms_per_window", {})
    ui.tiles([
        ui.tile("Detect · p50 / p95", f"{fmt(d.get('p50'))} ms", f"p95 {fmt(d.get('p95'))} ms · {fmt(d.get('n'))} flows"),
        ui.tile("Explain · p50 / p95", f"{fmt(e.get('p50'))} ms", f"p95 {fmt(e.get('p95'))} ms · {fmt(e.get('n'))} flows"),
        ui.tile("End-to-end per window · p95", f"{fmt(w.get('p95'))} ms", "budget: 1,000 ms window"),
        ui.tile("Flows replayed", ui.compact(lat.get("total_flows", 0)), f"{lat.get('windows', '–')} windows · {lat.get('scenario', '')}"),
    ])
    states = lat.get("by_state", {})
    if states:
        rows = [[s, fmt(v.get("windows")), fmt(v.get("flows")),
                 f"{v['pct_scored']:.1f}%" if v.get("pct_scored") is not None else "–",
                 f"{v['pct_explained']:.1f}%" if v.get("pct_explained") is not None else "–"]
                for s, v in states.items()]
        ui.html('<div class="fl-card">' + ui.table(rows, ["State", "Windows", "Flows", "Scored", "Explained"]) + "</div>")


def results_tab():
    top_l, top_r = st.columns([5, 1])
    with top_l:
        ui.html(f'<div style="color:{ui.MUTED};font-size:0.85rem;margin-top:6px">'
                "Offline evaluation results from <code>reports/</code>.</div>")
    with top_r:
        if st.button("Reload reports", width="stretch"):
            st.rerun()
    shap_benchmark()
    classification()
    holdout()
    pipeline_latency()
