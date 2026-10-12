"""Live dashboard (M3.2-M3.5). Reads data/events.db (written by the pipeline) and reports/*.

    streamlit run dashboard/app.py

Read-only: the dashboard never writes to the DB. It copes with the DB being
missing or recreated (every pipeline run deletes it first).
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "events.db"
REPORTS = ROOT / "reports"

STATE_COLORS = {"NORMAL": "#1a7f37", "ELEVATED": "#cf222e"}

st.set_page_config(page_title="FlowLens", page_icon="🛰️", layout="wide")


# ---------- data ----------

def query(sql, params=()):
    """Run a SELECT on the events DB; empty DataFrame if the DB or table isn't there yet."""
    if not DB.exists():
        return pd.DataFrame()
    try:
        # mode=ro: never create the file, never write
        with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True, timeout=1) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError):
        return pd.DataFrame()


def is_low_confidence(row):
    """Both models ran (if_score present) but only one of them flagged the flow."""
    return pd.notna(row["if_score"]) and row["source"] in ("lgbm", "iforest")


def elevated_spans(windows):
    """[(start_ts, end_ts)] for each run of consecutive ELEVATED windows."""
    spans, start, prev = [], None, None
    for ts, state in zip(windows["ts"], windows["state"]):
        if state == "ELEVATED" and start is None:
            start = ts
        if state != "ELEVATED" and start is not None:
            spans.append((start, prev + 1))
            start = None
        prev = ts
    if start is not None:
        spans.append((start, prev + 1))
    return spans


# ---------- live tab ----------

def top_row(windows):
    last = windows.iloc[-1]
    color = STATE_COLORS.get(last["state"], "#57606a")
    recent = query("SELECT COUNT(*) AS n FROM alerts WHERE ts > ?", (float(last["ts"]) - 60,))
    alerts_60s = int(recent["n"].iloc[0]) if not recent.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f"<div style='background:{color};color:white;border-radius:8px;padding:14px;text-align:center'>"
        f"<div style='font-size:0.8rem;opacity:0.85'>STATE · t = {last['ts']:.0f}s</div>"
        f"<div style='font-size:1.7rem;font-weight:700'>{last['state']}</div></div>",
        unsafe_allow_html=True,
    )
    c2.metric("Flows/s", f"{int(last['flows']):,}")
    c3.metric("Packets/s", f"{int(last['packets']):,}")
    c4.metric("Alerts (last 60 s)", f"{alerts_60s:,}")


def traffic_chart(windows):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=windows["ts"], y=windows["flows"], name="Flows/s",
                             line=dict(color="#0969da", width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=windows["ts"], y=windows["z_score"], name="z-score",
                             line=dict(color="#bf8700", width=1.5, dash="dot")), secondary_y=True)
    # after the traces: plotly skips vrects on subplots that have no data yet
    for x0, x1 in elevated_spans(windows):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=STATE_COLORS["ELEVATED"], opacity=0.15,
                      line_width=0, layer="below")
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
                      title=dict(text="Traffic (red shading = ELEVATED)", font=dict(size=14), y=0.97))
    fig.update_xaxes(title_text="Simulated time (s)")
    fig.update_yaxes(title_text="Flows/s", secondary_y=False, rangemode="tozero")
    fig.update_yaxes(title_text="z-score", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, width="stretch")


def alert_table(alerts):
    st.subheader("Recent alerts")
    if alerts.empty:
        st.info("No alerts yet.")
        return
    table = pd.DataFrame({
        "ID": alerts["id"],
        "Time (s)": alerts["ts"],
        "Dst port": alerts["dst_port"],
        "Predicted": alerts["pred_label"],
        "Confidence": alerts["pred_prob"],
        "Source": alerts["source"],
        "Ground truth": alerts["true_label"],
        "Low conf.": alerts.apply(lambda r: "⚠️" if is_low_confidence(r) else "", axis=1),
    })
    st.dataframe(
        table, hide_index=True, width="stretch", height=420,
        column_config={
            "Time (s)": st.column_config.NumberColumn(format="%.0f"),
            "Dst port": st.column_config.NumberColumn(format="%d"),
            "Confidence": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
        },
    )


def explanation_panel(alerts):
    st.subheader("Why was it flagged?")
    if alerts.empty:
        st.info("Explanations appear here once alerts arrive.")
        return

    # a number input, not a selectbox: its options would change every refresh and reset the pick
    choice = st.number_input("Alert ID (0 = latest)", min_value=0, step=1, key="alert_id",
                             help="Take the ID from the alerts table.")
    alert_id = int(alerts["id"].iloc[0]) if choice == 0 else int(choice)
    row = query("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    if row.empty:
        st.warning(f"No alert #{alert_id} in this run.")
        return
    row = row.iloc[0]

    tags = f"**#{row['id']}** · predicted **{row['pred_label']}** ({row['pred_prob']:.2f}) · source `{row['source']}`"
    st.markdown(tags + f" · ground truth **{row['true_label']}**")
    if is_low_confidence(row):
        st.warning("⚠️ Low confidence: LightGBM and IsolationForest disagree on this flow.")

    try:
        feats = pd.DataFrame(json.loads(row["top_features"] or "[]"))
    except json.JSONDecodeError:
        feats = pd.DataFrame()

    chart_col, text_col = st.columns([3, 2])
    with chart_col:
        if not feats.empty:
            feats = feats.iloc[::-1]  # biggest contribution on top
            fig = go.Figure(go.Bar(
                x=feats["contribution"], y=feats["name"], orientation="h",
                marker_color="#cf222e",
                text=[f"value {v:,.2f} · p{p}" for v, p in zip(feats["value"], feats["percentile"])],
                textposition="auto",
            ))
            fig.update_layout(height=80 + 50 * len(feats), margin=dict(l=10, r=10, t=10, b=10),
                              xaxis_title="SHAP contribution toward anomalous")
            st.plotly_chart(fig, width="stretch")
    with text_col:
        for sentence in (row["explanation"] or "").splitlines():
            if sentence.strip():
                st.markdown(f"- {sentence}")

    if_score = "n/a (NORMAL window)" if pd.isna(row["if_score"]) else f"{row['if_score']:.3f}"
    st.caption(f"t = {row['ts']:.0f}s · dst port {row['dst_port']} · IForest score {if_score} · "
               f"detect {row['detect_ms']:.3f} ms · explain {row['explain_ms']:.3f} ms")


def live_view():
    windows = query("SELECT * FROM traffic_windows ORDER BY ts")
    if windows.empty:
        st.info("Waiting for the pipeline… start it with "
                "`python -m pipeline.run --scenario scenarios/demo.json --speed 1`")
        return
    top_row(windows)
    traffic_chart(windows)

    alerts = query("SELECT * FROM alerts ORDER BY id DESC LIMIT 50")
    alert_table(alerts)
    explanation_panel(alerts)


# ---------- sidebar ----------

def pct(part, whole):
    return f"{100 * part / whole:.1f}%" if whole else "–"


def stats_sidebar():
    st.header("Live stats")
    lat = query("SELECT detect_ms, explain_ms FROM alerts")
    if lat.empty:
        st.caption("No alerts yet.")
    else:
        st.markdown("**Latency per flagged flow (ms)**")
        st.dataframe(pd.DataFrame({
            "p50": [lat["detect_ms"].quantile(0.5), lat["explain_ms"].quantile(0.5)],
            "p95": [lat["detect_ms"].quantile(0.95), lat["explain_ms"].quantile(0.95)],
        }, index=["Detect", "Explain"]).style.format("{:.3f}"), width="stretch")

    by_state = query("SELECT state, COUNT(*) AS windows, SUM(flows) AS flows, "
                     "SUM(scored) AS scored, SUM(explained) AS explained "
                     "FROM traffic_windows GROUP BY state")
    if not by_state.empty:
        st.markdown("**Work done per state**")
        st.dataframe(pd.DataFrame({
            "Windows": by_state["windows"].values,
            "Flows": by_state["flows"].values,
            "% scored": [pct(s, f) for s, f in zip(by_state["scored"], by_state["flows"])],
            "% explained": [pct(e, f) for e, f in zip(by_state["explained"], by_state["flows"])],
        }, index=by_state["state"]), width="stretch")

    meta = query("SELECT key, value FROM run_meta")
    if not meta.empty:
        st.markdown("**Run finished**")
        meta["value"] = meta["value"].map(lambda v: f"{float(v):,.3f}".rstrip("0").rstrip(".")
                                          if v.replace(".", "", 1).isdigit() else v)
        st.dataframe(meta.set_index("key"), width="stretch")


# ---------- results tab ----------

def load_report(name):
    path = REPORTS / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def show_json(data):
    """Dicts of dicts become a table; anything else falls back to raw JSON."""
    if isinstance(data, dict) and data and all(isinstance(v, dict) for v in data.values()):
        try:
            st.dataframe(pd.DataFrame(data).T, width="stretch")
            return
        except ValueError:
            pass
    if isinstance(data, list) and data and all(isinstance(v, dict) for v in data):
        st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
        return
    st.json(data)


def show_figure(name):
    path = REPORTS / "figures" / name
    if path.exists():
        st.image(str(path), width="stretch")


def results_tab():
    sections = [
        ("Classification (LightGBM vs RF)", "results.json", ["confusion_lgbm.png", "per_class_f1.png"]),
        ("Leave-one-attack-out holdout", "holdout.json", []),
        ("TreeSHAP vs Kernel SHAP", "explain_benchmark.json", ["shap_latency.png"]),
    ]
    for title, report, figures in sections:
        st.subheader(title)
        data = load_report(report)
        if data is None:
            st.info(f"`reports/{report}` not available yet (Member 1).")
        else:
            show_json(data)
        cols = st.columns(max(len(figures), 1))
        for col, fig in zip(cols, figures):
            with col:
                show_figure(fig)

    st.subheader("Pipeline latency (stress run)")
    lat = load_report("pipeline_latency.json")
    if lat is None:
        st.info("`reports/pipeline_latency.json` not available yet. "
                "Run `python -m pipeline.latency_report --scenario scenarios/stress.json`.")
        return
    st.caption(f"{lat.get('scenario')} · {lat.get('windows')} windows · {lat.get('total_flows', 0):,} flows")
    st.dataframe(pd.DataFrame({k: lat[k] for k in ["detect_ms", "explain_ms", "e2e_ms_per_window"] if k in lat}).T,
                 width="stretch")
    if "by_state" in lat:
        st.dataframe(pd.DataFrame(lat["by_state"]).T, width="stretch")


# ---------- page ----------

st.title("FlowLens · explainable real-time anomaly detection")
with st.sidebar:
    paused = st.toggle("Pause live updates", help="Freeze the view while you talk through an alert.")
    refresh = None if paused else 1  # seconds
    st.fragment(stats_sidebar, run_every=refresh)()

live, results = st.tabs(["Live", "Results"])
with live:
    st.fragment(live_view, run_every=refresh)()
with results:
    results_tab()
