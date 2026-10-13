# FlowLens

**Explainable real-time network anomaly detection.** FlowLens replays labelled network flows from CIC-IDS2017 as a live stream, detects attacks with LightGBM and Isolation Forest, and explains every alert with TreeSHAP, fast enough to run per flow while traffic is still arriving. A Streamlit dashboard shows traffic, alerts and the reasons behind each alert as they happen.

> VIT Computer Networks project. Full design: [docs/PLAN.md](docs/PLAN.md) · progress: [docs/STATUS.md](docs/STATUS.md)

## Why

Monitoring tools usually separate **visibility** (traffic dashboards) from **security** (alerts), and an ML alert arrives as a label with no reason. Research on explainable intrusion detection mostly explains detections offline with **Kernel SHAP**, which is far too slow to run on live traffic. FlowLens shows that per-flow explanations are cheap enough for real-time use if you:

1. use **tree models** and explain them with **TreeSHAP** (exact and fast) instead of Kernel SHAP, and
2. do the heavy work only when traffic looks abnormal, with a **two-tier design**.

## How it works

```
scenario.json ─▶ Replayer ─▶ Tier 1: EWMA monitor ─▶ Tier 2: detector ─▶ Explainer ─▶ SQLite (WAL) ─▶ Dashboard
                 1-s windows   NORMAL / ELEVATED      LightGBM (+ IForest)   TreeSHAP      events.db        Streamlit
```

| Stage | What it does |
|---|---|
| **Replayer** | Streams flows from the held-out test split in 1-second windows, following a scenario file (benign stretches, attack bursts). |
| **Tier 1** | An EWMA z-score on flows per window. **ELEVATED** after 3 windows with z > 3; back to **NORMAL** after 5 windows with z < 2. |
| **Tier 2** | NORMAL: LightGBM scores a random 10% of flows. ELEVATED: every flow is scored by LightGBM **and** Isolation Forest (for unseen attacks). |
| **Explainer** | TreeSHAP on flagged flows only. The top 3 features become sentences such as `Flow Packets/s = 4,812 (above 99.9% of normal flows)`. |
| **Dashboard** | Reads `data/events.db` once per second: traffic state, alerts, explanations, latency, and offline results. |

## Quick start

Requires **Python 3.11** (3.12 also works).

```bash
git clone https://github.com/krishitag/flowlens.git
cd flowlens
python -m venv .venv
```

Activate the environment and install the dependencies:

| OS | Activate |
|---|---|
| Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
| Windows (Git Bash) | `source .venv/Scripts/activate` |
| macOS / Linux | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
```

On macOS, LightGBM also needs OpenMP: `brew install libomp`.

### Get the models and data

**Option A, the real thing.** Download the processed data from the team Drive, **[link to be added by Member 1]**, into `data/processed/`. Then train the models (or pull them from `main`, where they're committed):

```bash
python ml/prepare.py      # only if you start from the raw CSVs in data/raw/
python ml/train.py        # writes models/*
python ml/evaluate.py     # writes reports/results.json + figures
```

**Option B, try it in a minute.** Generate fake models and test data that follow every contract:

```bash
python tests/make_fake_models.py
```

Don't commit these fake files (`models/` isn't gitignored), and never run this once real models are in `models/`, because it overwrites them.

### Run the live demo

Use two terminals, both started from the repo root:

```bash
streamlit run dashboard/app.py
```

```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```

Open http://localhost:8501. The demo takes about 105 seconds: benign traffic, a DoS burst, benign, a port scan, then benign again. You can start the two in either order. The dashboard waits for data and copes with the database being recreated on every run.

Always launch Streamlit **from the repo root**. That's where it finds `.streamlit/config.toml` (the dark theme).

## Dashboard

| Area | What you see |
|---|---|
| **Status strip** | LIVE / PAUSED / RUN COMPLETE, simulated time, windows, flows replayed, total alerts |
| **KPI tiles** | Traffic state (green NORMAL / red ELEVATED), flows/s against the normal baseline, packets/s, alerts in the last 60 s, Tier-2 coverage of the latest window |
| **Traffic** | Flows/s and the Tier-1 z-score on a shared time axis, with the enter/exit thresholds and ELEVATED periods shaded |
| **Alerts by type** | Alert counts per predicted class, and which model flagged them |
| **Recent alerts** | The last 50 alerts: dst port, prediction, confidence, model, ground truth, whether the prediction was correct, and a low-confidence flag |
| **Why was it flagged?** | The selected alert's SHAP contributions and plain-language reasons. Enter an alert ID to pin it; 0 follows the newest |
| **Sidebar** | Detect/explain latency p50/p95, % of flows scored and explained per state, run summary. **Pause live updates** freezes the screen while presenting |
| **Results tab** | TreeSHAP vs Kernel SHAP speed-up, classification metrics and per-class F1, leave-one-attack-out recall, pipeline latency (from `reports/`). Click **Reload reports** after new ones land |
| **How it works tab** | The pipeline, a guide to reading the dashboard, and the known limitation |

## Scenarios

| File | What it shows |
|---|---|
| `scenarios/demo.json` | Benign → DoS → benign → PortScan → benign (~105 s). Used for the live demo |
| `scenarios/stress.json` | High rates, replayed at full speed for the latency numbers |
| `scenarios/slowscan.json` | A low-rate port scan hidden in normal traffic: the known limitation |

`--speed 1` runs in real time, `--speed 0` as fast as possible.

## Results and evaluation

```bash
python ml/evaluate.py                                                 # macro/per-class F1, benign FPR, confusion matrix
python ml/holdout.py                                                  # leave-one-attack-out recall
python ml/benchmark_explain.py                                        # TreeSHAP vs Kernel SHAP latency
python -m pipeline.latency_report --scenario scenarios/stress.json   # end-to-end pipeline latency
python paper/build.py                                                 # rebuild paper/paper.md with the latest numbers
```

All results land in `reports/` and appear in the dashboard's **Results** tab.

## Tests

```bash
pytest tests/ -q
```

## Project layout

```
contracts/schema.sql   SQLite schema shared by pipeline and dashboard
dashboard/             Streamlit app: app.py (live view), results.py (Results tab), ui.py (theme and components)
docs/                  PLAN.md (design + contracts), STATUS.md (progress), tasks/ (per-member task lists)
ml/                    data prep, training, evaluation, holdout and SHAP benchmark
models/                trained model artifacts (contract 4.1)
paper/                 paper sections, build script, demo script
pipeline/              replayer, monitor, detector, explainer, store, run
reports/               results JSON + figures
scenarios/             replay scenarios
tests/                 unit tests + fake model generator
data/                  raw/processed data and events.db (gitignored, never committed)
```

## Known limitation

Low-and-slow attacks, such as a slow port scan, may never raise traffic enough to trigger ELEVATED. In the NORMAL state they are only caught by the 10% sample. That is the cost of tiering, and `scenarios/slowscan.json` demonstrates it.

## Troubleshooting

| Problem | Fix |
|---|---|
| The dashboard says "Waiting for the pipeline" | Start `python -m pipeline.run ...` from the repo root, so it writes to `data/events.db` |
| The dashboard is light-themed | Launch Streamlit from the repo root so it reads `.streamlit/config.toml` |
| `TypeError` mentioning `width` in Streamlit | Your Streamlit is too old: `pip install -U streamlit` |
| LightGBM import error on macOS | `brew install libomp` |
| A Results section says "not available yet" | That report hasn't been generated yet (see Results and evaluation above), then click **Reload reports** |

## Team

| Member | Area |
|---|---|
| Member 1 | ML and evaluation (`ml/`, `models/`, reports) |
| Member 2 | Streaming pipeline and explanations (`pipeline/`, `scenarios/`, `tests/`) |
| Member 3 | Dashboard, paper and demo (`dashboard/`, `paper/`, `README.md`) |

Dataset: [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html), Canadian Institute for Cybersecurity, University of New Brunswick.
