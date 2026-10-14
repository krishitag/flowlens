# FlowLens

**Explainable real-time network anomaly detection.** FlowLens replays labelled network flows from CIC-IDS2017 as a live stream, detects attacks with LightGBM and an Isolation Forest, and explains each alert with TreeSHAP while traffic is still arriving. A Streamlit dashboard shows traffic, alerts and the reasons behind each alert as they happen.

> VIT Computer Networks project. Full design: [docs/PLAN.md](docs/PLAN.md) · progress: [docs/STATUS.md](docs/STATUS.md) · paper: [paper/paper.md](paper/paper.md)

## Why

Monitoring tools usually separate **visibility** (traffic dashboards) from **security** (alerts), and an ML alert arrives as a label with no reason. Research on explainable intrusion detection mostly explains detections offline with **Kernel SHAP**, which is far too slow for live traffic. FlowLens shows that per-flow explanations are cheap enough for real-time use if you:

1. use **tree models** and explain them with **TreeSHAP** (exact and fast) instead of Kernel SHAP, and
2. do the heavy work only when traffic looks abnormal, with a **two-tier design**.

## Results

All numbers come from the real CIC-IDS2017 data and are reproduced by the scripts in [Evaluation](#evaluation).

| What | Result |
|---|---|
| Explanation time per flow | **TreeSHAP 2.4 ms vs Kernel SHAP ~2–2.6 s: ~800–1,100× faster** (median; Kernel SHAP varies run to run) |
| Classification (test set) | Macro F1 **0.972** (LightGBM), 0.986 (Random Forest baseline); LightGBM flags 0.37% of benign flows |
| Weakest classes | WebAttack (F1 0.86) and Bot (0.95), the two smallest classes |
| Unseen attacks (leave-one-attack-out) | DoS held out: 37.8% still caught (Isolation Forest 33%, LightGBM 5%). Bot held out: 0% |
| Pipeline under stress (~1,100 flows/s) | 223 ms per 1-second window at p95, well inside the 1,000 ms budget |
| Live demo | 6,550 alerts, 99.7% of them explained |

The honest weak spots, a low-and-slow scan and attacks that look like normal flows, are under [Known limitations](#known-limitations).

## How it works

```
scenario.json ─▶ Replayer ─▶ Tier 1: EWMA monitor ─▶ Tier 2: detector ─▶ Explainer ─▶ SQLite (WAL) ─▶ Dashboard
                 1-s windows   NORMAL / ELEVATED      LightGBM (+ IForest)   TreeSHAP      events.db        Streamlit
```

| Stage | What it does |
|---|---|
| **Replayer** | Streams flows from the held-out test split in 1-second windows, following a scenario file (benign stretches, attack bursts). |
| **Tier 1** | An EWMA z-score on flows per window. **ELEVATED** after 3 windows with z > 3; back to **NORMAL** after 5 windows with z < 2. |
| **Tier 2** | NORMAL: LightGBM scores a random 10% of flows. ELEVATED: every flow is scored by LightGBM **and** the Isolation Forest (for unseen attacks). |
| **Explainer** | TreeSHAP on flagged flows only, at most 300 per window (most confident first) so a heavy window stays inside its 1-second budget. The top 3 features become sentences such as `Flow Packets/s = 4,812 (above 99.9% of normal flows)`. |
| **Dashboard** | Reads `data/events.db` once per second: traffic state, alerts, explanations, latency, and the offline results. |

The models use 20 flow features (`models/features.json`). Destination port, IP addresses, flow IDs and timestamps are never used as features, because they would leak the answer.

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

That's all you need for the demo. The trained models (`models/`) and the test split (`data/processed/test.parquet`) come with the clone.

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
| **Why was it flagged?** | The selected alert's SHAP contributions and plain-language reasons. Enter an alert ID to pin it; 0 follows the newest. Alerts over the 300-per-window cap say "Not explained: per-window explanation budget reached" |
| **Sidebar** | Detect/explain latency p50/p95, % of flows scored and explained per state, run summary. **Pause live updates** freezes the screen while presenting |
| **Results tab** | TreeSHAP vs Kernel SHAP speed-up, classification metrics and per-class F1, leave-one-attack-out recall, pipeline latency (from `reports/`). Click **Reload reports** after new ones land |
| **How it works tab** | The pipeline, a guide to reading the dashboard, and the known limitation |

## Scenarios

| File | What it shows |
|---|---|
| `scenarios/demo.json` | Benign → DoS → benign → PortScan → benign (~105 s). Used for the live demo |
| `scenarios/stress.json` | High rates, replayed at full speed for the latency numbers |
| `scenarios/slowscan.json` | A low-rate port scan hidden in normal traffic: the known limitation |

`--speed 1` runs in real time, `--speed 0` as fast as possible. `--explain-cap N` changes the per-window explanation limit (default 300).

## Evaluation

These work straight after cloning:

```bash
python ml/evaluate.py                                                 # macro/per-class F1, benign FPR, confusion matrix
python -m pipeline.latency_report --scenario scenarios/stress.json   # end-to-end pipeline latency
pytest tests/ -q                                                      # unit tests
python paper/build.py                                                 # rebuild paper/paper.md with the latest numbers
```

Results land in `reports/` and appear in the dashboard's **Results** tab.

### Retraining and the full benchmarks

Retraining, the leave-one-attack-out test and the SHAP benchmark also need the training split, which is too large to keep in git. To rebuild it:

1. Download **CIC-IDS2017 MachineLearningCVE** (the 8 per-day CSVs, ~850 MB) from Kaggle, for example [chethuhn/network-intrusion-dataset](https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset), or from the [official UNB page](https://www.unb.ca/cic/datasets/ids-2017.html).
2. Put the CSVs directly in `data/raw/`.
3. Run:

```bash
python ml/prepare.py            # cleans, groups labels, writes data/processed/{train,val,test}.parquet (fixed seed)
python ml/train.py              # rebuilds models/*  (~30 s)
python ml/holdout.py            # leave-one-attack-out recall (DoS, Bot)
python ml/benchmark_explain.py  # TreeSHAP vs Kernel SHAP (~6 min, Kernel SHAP is the slow part)
```

`prepare.py` uses a fixed seed, so with the same CSVs it should rebuild the `test.parquet` that's in git.

## Project layout

```
contracts/schema.sql   SQLite schema shared by pipeline and dashboard
dashboard/             Streamlit app: app.py (live view), results.py (Results tab), ui.py (theme and components)
docs/                  PLAN.md (design + contracts), STATUS.md (progress), tasks/ (per-member task lists)
ml/                    data prep, training, evaluation, holdout and SHAP benchmark
models/                trained models, feature list, labels, IForest threshold, benign baselines
paper/                 paper sections, build script, demo script
pipeline/              replayer, monitor, detector, explainer, store, run, latency report
reports/               results JSON + figures
scenarios/             replay scenarios
tests/                 unit tests + fake model generator (development only)
data/                  gitignored, except data/processed/test.parquet (the replayed test split)
```

## Known limitations

- **Low-and-slow attacks.** A slow port scan may never raise traffic enough to trigger ELEVATED, so in the NORMAL state it is only caught by the 10% sample. `scenarios/slowscan.json` demonstrates it: the system stays NORMAL and catches 15 of 153 scan flows.
- **Attacks that look normal.** At its 1% false-positive threshold, the Isolation Forest catches a third of DoS flows but almost none of the other attacks, so a new attack type that resembles normal traffic (Bot, in our test) can go undetected.
- **Unexplained alerts under heavy load.** Above 300 flagged flows in one window, the least confident alerts are stored without an explanation.
- **Replayed traffic.** Flows come from labelled CSV records, not live packet capture, so the latency numbers exclude capture and feature extraction.

## Troubleshooting

| Problem | Fix |
|---|---|
| The dashboard says "Waiting for the pipeline" | Start `python -m pipeline.run ...` from the repo root, so it writes to `data/events.db` |
| The dashboard is light-themed | Launch Streamlit from the repo root so it reads `.streamlit/config.toml` |
| `TypeError` mentioning `width` in Streamlit | Your Streamlit is too old: `pip install -U streamlit` |
| LightGBM import error on macOS | `brew install libomp` |
| `ml/holdout.py` or `ml/benchmark_explain.py` can't find `train.parquet` | Rebuild it: see [Retraining and the full benchmarks](#retraining-and-the-full-benchmarks) |
| A Results section says "not available yet" | That report hasn't been generated yet (see [Evaluation](#evaluation)), then click **Reload reports** |

`tests/make_fake_models.py` writes synthetic models and data for development without the dataset. Don't run it in this repo: it overwrites the real `models/` and `test.parquet`.

## Team

| Member | Area |
|---|---|
| Member 1 | ML and evaluation (`ml/`, `models/`, reports); later handled by Member 2 |
| Member 2 | Streaming pipeline and explanations (`pipeline/`, `scenarios/`, `tests/`), and the final ML |
| Member 3 | Dashboard, paper and demo (`dashboard/`, `paper/`, `README.md`) |

Dataset: [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html), Canadian Institute for Cybersecurity, University of New Brunswick.
