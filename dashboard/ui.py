"""Look and feel for the dashboard: colours, CSS, Plotly layout and small HTML components.

Black/grey theme. Colour is reserved for status (NORMAL / ELEVATED / low confidence);
every chart is a single neutral series, so identity is never carried by hue.
"""
from html import escape

import streamlit as st

# palette (dark chart chrome from the team's dataviz reference)
PAGE = "#0d0d0d"
SURFACE = "#1a1a19"
SURFACE_2 = "#222220"
BORDER = "rgba(255,255,255,0.10)"
INK = "#ededeb"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
SERIES = "#d6d5ce"  # the one data colour

GOOD = "#0ca30c"
WARNING = "#fab219"
CRITICAL = "#d03b3b"
STATE_COLORS = {"NORMAL": GOOD, "ELEVATED": CRITICAL}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
.stApp {{ background: {PAGE}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"], .block-container {{
  padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1480px;
}}
[data-testid="stSidebar"] {{ background: #111110; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding-top: 0.6rem; }}
footer, #MainMenu, [data-testid="stAppDeployButton"] {{ display: none; }}
code {{ color: {INK_2} !important; background: {SURFACE_2} !important; border-radius: 4px; padding: 1px 5px; }}
h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}

/* tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{
  height: 40px; padding: 0 16px; background: transparent; color: {MUTED};
  font-weight: 500; border-radius: 6px 6px 0 0;
}}
.stTabs [aria-selected="true"] {{ color: {INK}; background: {SURFACE}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background: {INK_2}; }}

/* plotly + dataframe frames */
[data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 6px;
}}
[data-testid="stDataFrame"] {{ padding: 0; overflow: hidden; }}

/* header */
.fl-header {{ display:flex; align-items:center; justify-content:space-between; gap:16px;
  flex-wrap:wrap; margin-bottom: 18px; }}
.fl-brand {{ display:flex; align-items:center; gap:12px; }}
.fl-logo {{ width:36px; height:36px; border-radius:9px; background:{SURFACE_2};
  border:1px solid {BORDER}; display:grid; place-items:center; }}
.fl-title {{ font-size:1.35rem; font-weight:700; color:{INK}; line-height:1.1; }}
.fl-sub {{ font-size:0.82rem; color:{MUTED}; }}

/* status strip */
.fl-strip {{ display:flex; align-items:center; gap:18px; flex-wrap:wrap; color:{MUTED};
  font-size:0.8rem; margin: 2px 0 14px; }}
.fl-strip b {{ color:{INK_2}; font-weight:500; }}
.fl-pill {{ display:inline-flex; align-items:center; gap:7px; padding:3px 10px;
  border-radius:999px; border:1px solid {BORDER}; background:{SURFACE}; color:{INK_2};
  font-size:0.72rem; font-weight:600; letter-spacing:0.06em; }}
.fl-dot {{ width:7px; height:7px; border-radius:50%; background:{MUTED}; }}
.fl-dot.live {{ background:{GOOD}; box-shadow:0 0 0 0 rgba(12,163,12,.6); animation: fl-pulse 1.6s infinite; }}
@keyframes fl-pulse {{ 0%{{box-shadow:0 0 0 0 rgba(12,163,12,.55)}} 70%{{box-shadow:0 0 0 7px rgba(12,163,12,0)}} 100%{{box-shadow:0 0 0 0 rgba(12,163,12,0)}} }}

/* stat tiles */
.fl-tiles {{ display:grid; grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr)); gap:12px; margin-bottom:14px; }}
@media (max-width: 900px) {{ .fl-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 520px) {{ .fl-tiles {{ grid-template-columns: 1fr; }} }}
.fl-tile {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:14px 16px; min-height:96px; }}
.fl-tile .lbl {{ font-size:0.75rem; color:{MUTED}; font-weight:500; }}
.fl-tile .val {{ font-size:clamp(1.25rem, 2vw, 1.75rem); font-weight:600; color:{INK}; margin-top:4px; line-height:1.15; }}
.fl-tile .note {{ font-size:0.75rem; color:{MUTED}; margin-top:4px; }}
.fl-tile.state {{ border-left-width:4px; }}
.fl-state {{ display:flex; align-items:center; gap:8px; }}

/* section heading */
.fl-section {{ display:flex; align-items:baseline; justify-content:space-between; margin: 22px 0 10px; }}
.fl-section h3 {{ font-size:1.02rem; font-weight:600; margin:0; padding:0; }}
.fl-section span {{ font-size:0.78rem; color:{MUTED}; }}

/* cards, badges, tables */
.fl-card {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:16px 18px; }}
.fl-badge {{ display:inline-block; padding:2px 9px; border-radius:6px; font-size:0.74rem; font-weight:600;
  border:1px solid {BORDER}; background:{SURFACE_2}; color:{INK_2}; }}
.fl-badge.mono {{ font-family:'JetBrains Mono', monospace; font-weight:500; }}
.fl-warn {{ display:flex; gap:8px; align-items:flex-start; padding:9px 12px; border-radius:8px;
  border:1px solid rgba(250,178,25,.35); background:rgba(250,178,25,.08); color:{INK}; font-size:0.84rem; margin-top:10px; }}
.fl-kv {{ display:grid; grid-template-columns: auto 1fr; gap:6px 14px; font-size:0.82rem; margin-top:12px; }}
.fl-kv dt {{ color:{MUTED}; }} .fl-kv dd {{ color:{INK_2}; margin:0; text-align:right;
  font-variant-numeric: tabular-nums; }}
.fl-big {{ font-size:1.6rem; font-weight:700; color:{INK}; margin:6px 0 2px; }}
.fl-reasons {{ list-style:none; padding:0; margin:0; }}
.fl-reasons li {{ padding:10px 12px; border:1px solid {BORDER}; border-radius:8px; margin-bottom:8px;
  background:{SURFACE_2}; color:{INK}; font-size:0.86rem; }}
.fl-reasons li span {{ display:block; color:{MUTED}; font-size:0.74rem; margin-bottom:2px; }}
.fl-table {{ width:100%; border-collapse:collapse; font-size:0.8rem; border:none !important; margin:0; }}
.fl-table tr, .fl-table th, .fl-table td {{ border-left:none !important; border-right:none !important; border-top:none !important; background:transparent !important; }}
.fl-table th {{ text-align:right; color:{MUTED}; font-weight:500; padding:6px 4px; border-bottom:1px solid {BORDER}; }}
.fl-table th:first-child, .fl-table td:first-child {{ text-align:left; }}
.fl-table td {{ text-align:right; color:{INK_2}; padding:6px 4px; border-bottom:1px solid {GRID};
  font-variant-numeric: tabular-nums; }}
.fl-side-h {{ font-size:0.7rem; letter-spacing:0.08em; text-transform:uppercase; color:{MUTED};
  font-weight:600; margin:18px 0 8px; }}
.fl-empty {{ text-align:center; padding:56px 20px; border:1px dashed {AXIS}; border-radius:12px; color:{MUTED}; }}
.fl-empty h4 {{ color:{INK}; margin-bottom:6px; }}
.fl-empty code {{ color:{INK_2}; }}
.fl-steps {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap:12px; }}
.fl-step {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:14px 16px; }}
.fl-step .n {{ font-family:'JetBrains Mono', monospace; color:{MUTED}; font-size:0.72rem; }}
.fl-step .t {{ color:{INK}; font-weight:600; margin:4px 0 6px; }}
.fl-step .d {{ color:{INK_2}; font-size:0.82rem; line-height:1.45; }}
</style>
"""

LOGO = f"""<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{INK}" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg>"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def header():
    html(f"""<div class="fl-header"><div class="fl-brand"><div class="fl-logo">{LOGO}</div>
      <div><div class="fl-title">FlowLens</div>
      <div class="fl-sub">Explainable real-time network anomaly detection · CIC-IDS2017</div></div></div></div>""")


def section(title, note=""):
    html(f'<div class="fl-section"><h3>{escape(title)}</h3><span>{escape(note)}</span></div>')


def tile(label, value, note="", accent=None):
    """One stat tile. `accent` colours the left border and a dot before the value (state tiles)."""
    if accent:
        return (f'<div class="fl-tile state" style="border-left-color:{accent}"><div class="lbl">{escape(label)}</div>'
                f'<div class="val fl-state"><span class="fl-dot" style="background:{accent};width:10px;height:10px"></span>'
                f'{escape(value)}</div><div class="note">{escape(note)}</div></div>')
    return (f'<div class="fl-tile"><div class="lbl">{escape(label)}</div><div class="val">{escape(value)}</div>'
            f'<div class="note">{escape(note)}</div></div>')


def tiles(items, cols=None):
    """A row of stat tiles; `cols` defaults to one row (max 4 per row)."""
    cols = cols or min(len(items), 4)
    html(f'<div class="fl-tiles" style="--cols:{cols}">' + "".join(items) + "</div>")


def badge(text, mono=False, color=None):
    style = f' style="color:{color};border-color:{color}55"' if color else ""
    return f'<span class="fl-badge{" mono" if mono else ""}"{style}>{escape(str(text))}</span>'


def table(rows, columns=None):
    """Small HTML table for the sidebar/results; first column left-aligned. No header if `columns` is None."""
    head = "".join(f"<th>{escape(c)}</th>" for c in columns) if columns else ""
    body = "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in r) + "</tr>" for r in rows)
    thead = f"<thead><tr>{head}</tr></thead>" if head else ""
    return f'<table class="fl-table">{thead}<tbody>{body}</tbody></table>'


def empty(title, body_html):
    html(f'<div class="fl-empty"><h4>{escape(title)}</h4>{body_html}</div>')


def compact(n):
    """1,284 / 12.9K / 4.2M"""
    n = float(n)
    for unit, size in (("M", 1e6), ("K", 1e4)):
        if abs(n) >= size:
            return f"{n / (size if unit == 'M' else 1e3):.1f}{unit}"
    return f"{n:,.0f}"


def plot_layout(fig, height, **extra):
    """Shared dark Plotly chrome: transparent surfaces, hairline grid, muted axes."""
    fig.update_layout(
        template="plotly_dark", height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=INK_2, size=12),
        margin=dict(l=12, r=12, t=16, b=12), showlegend=False,
        hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=AXIS, font=dict(color=INK, size=12)),
        **extra,
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig
