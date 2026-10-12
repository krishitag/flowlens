"""FlowLens live dashboard (M3.2-M3.5). Reads data/events.db (written by the pipeline) and reports/*.

    streamlit run dashboard/app.py

Read-only: the dashboard never writes to the DB. It copes with the DB being
missing or recreated (every pipeline run deletes it first).
"""
import json
import sqlite3
import time
from html import escape
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import ui
from results import results_tab

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "events.db"
REPO_URL = "https://github.com/krishitag/flowlens"
Z_ON, Z_OFF = 3.0, 2.0  # Tier-1 thresholds (PLAN.md section 2), drawn on the z-score panel

st.set_page_config(page_title="FlowLens", page_icon="🛰️", layout="wide", initial_sidebar_state="auto")
ui.inject_css()


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


def seconds_since_write():
    """Age of the newest DB file (main or WAL); a running pipeline touches one every window."""
    times = [p.stat().st_mtime for p in (DB, Path(f"{DB}-wal")) if p.exists()]
    return time.time() - max(times) if times else None


def is_low_confidence(row):
    """Both models ran (if_score present) but only one of them flagged the flow."""
    return pd.notna(row["if_score"]) and row["source"] in ("lgbm", "iforest")


def step_alert(delta, latest_id):
    """Prev/Next/Latest buttons: move the pinned alert ID (0 = follow the newest)."""
    if delta == 0:
        st.session_state.alert_id = 0
        return
    current = st.session_state.get("alert_id") or latest_id
    new = max(1, current + delta)
    st.session_state.alert_id = 0 if new >= latest_id else new


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

def status_strip(windows, totals, paused, finished):
    age = seconds_since_write()
    if paused:
        pill = '<span class="fl-pill"><span class="fl-dot"></span>PAUSED</span>'
    elif finished:
        pill = '<span class="fl-pill"><span class="fl-dot" style="background:#c3c2b7"></span>RUN COMPLETE</span>'
    elif age is not None and age < 3:
        pill = '<span class="fl-pill"><span class="fl-dot live"></span>LIVE</span>'
    else:
        pill = '<span class="fl-pill"><span class="fl-dot" style="background:#fab219"></span>NO NEW DATA</span>'
    last = windows.iloc[-1]
    ui.html(f'<div class="fl-strip">{pill}'
            f'<span>Simulated time <b>{last["ts"]:.0f} s</b></span>'
            f'<span>Windows <b>{len(windows):,}</b></span>'
            f'<span>Flows replayed <b>{int(windows["flows"].sum()):,}</b></span>'
            f'<span>Alerts <b>{totals:,}</b></span></div>')


def kpi_tiles(windows, alerts_60s, total_alerts):
    last = windows.iloc[-1]
    state = last["state"]
    normal = windows[windows["state"] == "NORMAL"].tail(30)["flows"]
    baseline = f"Normal baseline ≈ {normal.median():.0f}/s" if len(normal) else ""
    coverage = last["scored"] / last["flows"] if last["flows"] else 0
    ui.tiles([
        ui.tile("Traffic state", state, f"z-score {last['z_score']:.2f}", accent=ui.STATE_COLORS.get(state, ui.MUTED)),
        ui.tile("Flows / s", f"{int(last['flows']):,}", baseline),
        ui.tile("Packets / s", ui.compact(last["packets"]), f"{last['bytes'] / 1e6:,.2f} MB/s"),
        ui.tile("Alerts · last 60 s", f"{alerts_60s:,}", f"{total_alerts:,} this run"),
        ui.tile("Tier-2 coverage", f"{coverage:.0%}",
                f"{int(last['scored']):,} scored · {int(last['explained']):,} explained"),
    ], cols=5)


def traffic_chart(windows):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.64, 0.36], vertical_spacing=0.07)
    fig.add_trace(go.Scatter(
        x=windows["ts"], y=windows["flows"], name="Flows/s", mode="lines",
        line=dict(color=ui.SERIES, width=2), fill="tozeroy", fillcolor="rgba(214,213,206,0.07)",
        hovertemplate="%{y:,} flows/s<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=windows["ts"], y=windows["z_score"], name="z-score", mode="lines",
        line=dict(color=ui.INK_2, width=1.5), hovertemplate="z = %{y:.2f}<extra></extra>"), row=2, col=1)

    # thresholds and ELEVATED bands go on after the traces (plotly skips empty subplots)
    fig.add_hline(y=Z_ON, row=2, col=1, line=dict(color=ui.CRITICAL, width=1, dash="dot"),
                  annotation_text=f"enter z > {Z_ON:g}", annotation_position="top right",
                  annotation_font=dict(color=ui.MUTED, size=10))
    fig.add_hline(y=Z_OFF, row=2, col=1, line=dict(color=ui.WARNING, width=1, dash="dot"),
                  annotation_text=f"exit z < {Z_OFF:g}", annotation_position="bottom right",
                  annotation_font=dict(color=ui.MUTED, size=10))
    for x0, x1 in elevated_spans(windows):
        fig.add_vrect(x0=x0, x1=x1, row="all", col=1, fillcolor=ui.CRITICAL, opacity=0.13,
                      line_width=0, layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=1.0, xref="x", yref="y domain", text="ELEVATED",
                           showarrow=False, yanchor="bottom", font=dict(color=ui.CRITICAL, size=10))

    ui.plot_layout(fig, 380, hovermode="x unified")
    fig.update_yaxes(title=dict(text="Flows/s", font=dict(color=ui.MUTED, size=11)), rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title=dict(text="z-score", font=dict(color=ui.MUTED, size=11)), row=2, col=1)
    fig.update_xaxes(title=dict(text="Simulated time (s)", font=dict(color=ui.MUTED, size=11)), row=2, col=1)
    fig.update_layout(margin=dict(l=12, r=12, t=26, b=12))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def attack_mix():
    mix = query("SELECT pred_label, COUNT(*) AS n FROM alerts GROUP BY pred_label ORDER BY n")
    sources = query("SELECT source, COUNT(*) AS n, SUM(if_score IS NOT NULL AND source != 'both') AS low "
                    "FROM alerts GROUP BY source")
    if mix.empty:
        ui.empty("No alerts yet", "<p>Detections appear here as they happen.</p>")
        return
    fig = go.Figure(go.Bar(
        x=mix["n"], y=mix["pred_label"], orientation="h",
        marker=dict(color=ui.SERIES, cornerradius=4),
        text=[f"{n:,}" for n in mix["n"]], textposition="outside", textfont=dict(color=ui.INK_2, size=11),
        hovertemplate="%{y}: %{x:,} alerts<extra></extra>",
    ))
    ui.plot_layout(fig, 60 + 34 * len(mix), bargap=0.35)
    fig.update_traces(cliponaxis=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, mix["n"].max() * 1.3])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=ui.INK_2))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    by_source = dict(zip(sources["source"], sources["n"]))
    low = int(sources["low"].fillna(0).sum())
    rows = [["LightGBM only", f"{by_source.get('lgbm', 0):,}"],
            ["Isolation Forest only", f"{by_source.get('iforest', 0):,}"],
            ["Both models", f"{by_source.get('both', 0):,}"],
            ["Low confidence (models disagree)", f"{low:,}"]]
    ui.html('<div class="fl-card" style="padding:10px 14px">' + ui.table(rows, ["Flagged by", "Alerts"]) + "</div>")


def alert_table(alerts):
    if alerts.empty:
        ui.empty("No alerts yet", "<p>Flagged flows will be listed here, newest first.</p>")
        return
    table = pd.DataFrame({
        "ID": alerts["id"],
        "Time (s)": alerts["ts"],
        "Dst port": alerts["dst_port"],
        "Predicted": alerts["pred_label"],
        "Confidence": alerts["pred_prob"],
        "Flagged by": alerts["source"].map({"lgbm": "LightGBM", "iforest": "IForest", "both": "Both"}),
        "Ground truth": alerts["true_label"],
        "Correct": (alerts["pred_label"] == alerts["true_label"]).map({True: "✓", False: "✗"}),
        "Low conf.": alerts.apply(lambda r: "⚠" if is_low_confidence(r) else "", axis=1),
    })
    st.dataframe(
        table, hide_index=True, width="stretch", height=388,
        column_config={
            "ID": st.column_config.NumberColumn(format="%d", width="small"),
            "Time (s)": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Dst port": st.column_config.NumberColumn(format="%d", width="small"),
            "Confidence": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
            "Correct": st.column_config.TextColumn(width="small", help="Prediction matches ground truth"),
            "Low conf.": st.column_config.TextColumn(width="small", help="Both models ran and disagreed"),
        },
    )


def explanation_panel(latest_id):
    ctrl, prev, nxt, latest, hint = st.columns([1.1, 0.75, 0.75, 0.9, 3], vertical_alignment="bottom")
    with ctrl:
        # a number input, not a selectbox: its options would change every refresh and reset the pick
        choice = st.number_input("Alert ID", min_value=0, step=1, key="alert_id",
                                 help="0 follows the newest alert. Take any ID from the table above.")
    current = latest_id if choice == 0 else int(choice)
    prev.button("◀ Prev", on_click=step_alert, args=(-1, latest_id), width="stretch",
                disabled=current <= 1, help="Previous alert")
    nxt.button("Next ▶", on_click=step_alert, args=(1, latest_id), width="stretch",
               disabled=choice == 0, help="Next alert")
    latest.button("Latest", on_click=step_alert, args=(0, latest_id), width="stretch",
                  type="primary" if choice != 0 else "secondary", help="Follow the newest alert")
    with hint:
        ui.html(f'<div style="color:{ui.MUTED};font-size:0.8rem;padding-bottom:8px">'
                + ("Following the newest alert. Step back with Prev, or pause live updates while presenting."
                   if choice == 0 else "Pinned. Press Latest to follow the newest alert again.") + "</div>")

    alert_id = latest_id if choice == 0 else int(choice)
    row = query("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    if row.empty:
        ui.empty(f"No alert #{alert_id} in this run", "<p>The pipeline recreates the database on every run.</p>")
        return
    row = row.iloc[0]

    meta, detail = st.columns([1, 2])
    with meta:
        correct = row["pred_label"] == row["true_label"]
        truth_color = ui.GOOD if correct else ui.CRITICAL
        source = {"lgbm": "LightGBM", "iforest": "Isolation Forest", "both": "LightGBM + IForest"}[row["source"]]
        if_score = "n/a · NORMAL window" if pd.isna(row["if_score"]) else f"{row['if_score']:.3f}"
        warn = ('<div class="fl-warn">⚠ <div><b>Low confidence.</b> Both models scored this flow '
                "but only one flagged it.</div></div>") if is_low_confidence(row) else ""
        ui.html(f"""<div class="fl-card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            {ui.badge(f"#{row['id']}", mono=True)} {ui.badge(source)}</div>
          <div style="color:{ui.MUTED};font-size:0.75rem;margin-top:14px">Predicted</div>
          <div class="fl-big">{escape(row['pred_label'])}</div>
          <div style="color:{ui.INK_2};font-size:0.85rem">confidence {row['pred_prob']:.2f}</div>
          <dl class="fl-kv">
            <dt>Ground truth</dt><dd>{ui.badge(("✓ " if correct else "✗ ") + row['true_label'], color=truth_color)}</dd>
            <dt>Time</dt><dd>{row['ts']:.0f} s</dd>
            <dt>Dst port</dt><dd>{int(row['dst_port'])}</dd>
            <dt>IForest score</dt><dd>{if_score}</dd>
            <dt>Detect</dt><dd>{row['detect_ms']:.3f} ms</dd>
            <dt>Explain</dt><dd>{row['explain_ms']:.3f} ms</dd>
          </dl>{warn}</div>""")

    with detail:
        try:
            feats = pd.DataFrame(json.loads(row["top_features"] or "[]"))
        except json.JSONDecodeError:
            feats = pd.DataFrame()
        if not feats.empty:
            feats = feats.iloc[::-1]  # biggest contribution on top
            fig = go.Figure(go.Bar(
                x=feats["contribution"], y=feats["name"], orientation="h",
                marker=dict(color=ui.SERIES, cornerradius=4),
                text=[f"{c:+.2f}" for c in feats["contribution"]], textposition="outside",
                textfont=dict(color=ui.INK_2, size=11),
                customdata=list(zip(feats["value"], feats["percentile"])),
                hovertemplate="%{y}<br>value %{customdata[0]:,.2f} · benign percentile %{customdata[1]}"
                              "<br>SHAP %{x:+.3f}<extra></extra>",
            ))
            ui.plot_layout(fig, 70 + 46 * len(feats), bargap=0.4)
            fig.update_xaxes(title=dict(text="SHAP contribution toward anomalous",
                                        font=dict(color=ui.MUTED, size=11)),
                             range=[0, feats["contribution"].max() * 1.2])
            fig.update_yaxes(showgrid=False, tickfont=dict(color=ui.INK_2))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        reasons = [s for s in (row["explanation"] or "").splitlines() if s.strip()]
        ui.html('<ul class="fl-reasons">' + "".join(reason_item(s) for s in reasons) + "</ul>")


def reason_item(sentence):
    """'Flow Packets/s = 4,812 (above 99.9% of normal flows)' -> feature name over 'value · comparison'."""
    if " = " not in sentence:
        return f"<li>{escape(sentence)}</li>"
    name, rest = sentence.split(" = ", 1)
    value, _, compare = rest.partition(" (")
    compare = compare.rstrip(")")
    body = f"<b>{escape(value)}</b>" + (f" · {escape(compare)}" if compare else "")
    return f"<li><span>{escape(name)}</span>{body}</li>"


def live_view(paused):
    windows = query("SELECT * FROM traffic_windows ORDER BY ts")
    if windows.empty:
        ui.empty("Waiting for the pipeline",
                 "<p>Start a run in another terminal. This page picks it up automatically.</p>"
                 "<code>python -m pipeline.run --scenario scenarios/demo.json --speed 1</code>")
        return

    last_ts = float(windows["ts"].iloc[-1])
    counts = query("SELECT COUNT(*) AS total, SUM(ts > ?) AS recent, MAX(id) AS latest FROM alerts", (last_ts - 60,))
    total = int(counts["total"].iloc[0]) if not counts.empty else 0
    recent = int(counts["recent"].fillna(0).iloc[0]) if not counts.empty else 0
    latest_id = counts["latest"].iloc[0] if total else None
    finished = not query("SELECT 1 FROM run_meta LIMIT 1").empty

    status_strip(windows, total, paused, finished)
    kpi_tiles(windows, recent, total)

    left, right = st.columns([2, 1])
    with left:
        ui.section("Traffic", "Tier-1 EWMA monitor · shaded = ELEVATED")
        traffic_chart(windows)
    with right:
        ui.section("Alerts by predicted type", "this run")
        attack_mix()

    ui.section("Recent alerts", "last 50 · newest first")
    alert_table(query("SELECT * FROM alerts ORDER BY id DESC LIMIT 50"))

    ui.section("Why was it flagged?", "TreeSHAP · top features pushing toward anomalous")
    if latest_id is None:
        ui.empty("Nothing to explain yet", "<p>Explanations appear with the first alert.</p>")
    else:
        explanation_panel(int(latest_id))


# ---------- sidebar ----------

def stats_sidebar():
    lat = query("SELECT detect_ms, explain_ms FROM alerts")
    ui.html('<div class="fl-side-h">Latency per flagged flow</div>')
    if lat.empty:
        ui.html(f'<div style="color:{ui.MUTED};font-size:0.8rem">No alerts yet.</div>')
    else:
        rows = [[name, f"{lat[col].quantile(0.5):.3f}", f"{lat[col].quantile(0.95):.3f}"]
                for name, col in (("Detect", "detect_ms"), ("Explain", "explain_ms"))]
        ui.html(ui.table(rows, ["ms", "p50", "p95"]))

    by_state = query("SELECT state, COUNT(*) AS windows, SUM(flows) AS flows, "
                     "SUM(scored) AS scored, SUM(explained) AS explained FROM traffic_windows GROUP BY state")
    ui.html('<div class="fl-side-h">Tier-2 workload by state</div>')
    if by_state.empty:
        ui.html(f'<div style="color:{ui.MUTED};font-size:0.8rem">No windows yet.</div>')
    else:
        rows = [[r.state, f"{int(r.windows):,}",
                 f"{100 * r.scored / r.flows:.1f}%" if r.flows else "–",
                 f"{100 * r.explained / r.flows:.1f}%" if r.flows else "–"] for r in by_state.itertuples()]
        ui.html(ui.table(rows, ["State", "Windows", "Scored", "Explained"]))

    meta = query("SELECT key, value FROM run_meta")
    if not meta.empty:
        m = dict(zip(meta["key"], meta["value"]))
        ui.html('<div class="fl-side-h">Run summary</div>')
        rows = [["Scenario", Path(m.get("scenario", "–")).name],
                ["Speed", m.get("speed", "–")],
                ["Flows", f"{int(float(m.get('total_flows', 0))):,}"],
                ["Alerts", f"{int(float(m.get('total_alerts', 0))):,}"]]
        ui.html(ui.table(rows))


def sidebar():
    ui.html(f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0 6px">'
            f'<div class="fl-logo" style="width:30px;height:30px">{ui.LOGO}</div>'
            f'<div style="font-weight:700;color:{ui.INK}">FlowLens</div></div>')
    ui.html('<div class="fl-side-h">Controls</div>')
    paused = st.session_state.get("paused", False)
    st.button("▶ Resume live" if paused else "❚❚ Pause live", key="pause_btn", on_click=toggle_pause,
              type="primary" if paused else "secondary", width="stretch",
              help="Freeze the view while you talk through an alert.")
    return paused


def toggle_pause():
    st.session_state.paused = not st.session_state.get("paused", False)


# ---------- how it works ----------

STEPS = [
    ("01", "Replayer", "Streams labelled CIC-IDS2017 test flows in 1-second windows, following a scenario file."),
    ("02", "Tier 1 · EWMA monitor", f"z-score of flows per window. ELEVATED after 3 windows with z > {Z_ON:g}; "
                                    f"back to NORMAL after 5 with z < {Z_OFF:g}."),
    ("03", "Tier 2 · detector", "NORMAL: LightGBM on a 10% sample. ELEVATED: every flow, LightGBM and Isolation Forest."),
    ("04", "Explainer", "TreeSHAP on flagged flows only. The top 3 features become sentences using benign percentiles."),
    ("05", "Store → dashboard", "SQLite in WAL mode. This page reads it once per second, read-only."),
]


def how_it_works():
    ui.section("Pipeline", "Explanations are cheap enough for live use with tree models and a two-tier design")
    ui.html('<div class="fl-steps">' + "".join(
        f'<div class="fl-step"><div class="n">{n}</div><div class="t">{escape(t)}</div><div class="d">{escape(d)}</div></div>'
        for n, t, d in STEPS) + "</div>")
    ui.section("Reading the dashboard")
    ui.html(f"""<div class="fl-card" style="color:{ui.INK_2};font-size:0.88rem;line-height:1.65">
      <b style="color:{ui.INK}">Traffic state</b> is green when NORMAL and red when ELEVATED. Red bands on the chart
      mark ELEVATED periods.<br>
      <b style="color:{ui.INK}">Flagged by</b> shows which model raised the alert. If only Isolation Forest flagged a
      flow and LightGBM says BENIGN, the flow is anomalous but unlike any known attack.<br>
      <b style="color:{ui.INK}">Low confidence ⚠</b> means both models scored the flow but only one flagged it.<br>
      <b style="color:{ui.INK}">SHAP contribution</b>: longer bars pushed the flow further toward "anomalous". The
      sentences compare each value with normal (benign) traffic.<br>
      <b style="color:{ui.INK}">Ground truth</b> is shown for demo honesty. A live deployment wouldn't have it.
    </div>""")
    ui.section("Known limitation")
    ui.html(f"""<div class="fl-card" style="color:{ui.INK_2};font-size:0.88rem;line-height:1.65">
      Low-and-slow attacks (for example a slow port scan) may never raise traffic enough to trigger ELEVATED. In the
      NORMAL state they are only caught by the 10% sample. That is the trade-off of tiering. Run
      <code>scenarios/slowscan.json</code> to see it.</div>""")


# ---------- page ----------

brand, links = st.columns([5, 1], vertical_alignment="center")
with brand:
    ui.header()
with links:
    st.link_button("GitHub ↗", REPO_URL, width="stretch")
with st.sidebar:
    paused = sidebar()
    refresh = None if paused else 1  # seconds
    st.fragment(stats_sidebar, run_every=refresh)()
    ui.html(f'<div style="color:{ui.MUTED};font-size:0.72rem;margin-top:24px">Reads <code>data/events.db</code> '
            "(read-only)</div>")

live, results, about = st.tabs(["Live monitor", "Results", "How it works"])
with live:
    st.fragment(live_view, run_every=refresh)(paused)
with results:
    results_tab()
with about:
    how_it_works()
