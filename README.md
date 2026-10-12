# flowlens

Real-time network anomaly detection with per-flow explanations: LightGBM + Isolation Forest with TreeSHAP, a two-tier traffic monitor, and a live Streamlit dashboard. Built on CIC-IDS2017.

The full plan is in [docs/PLAN.md](docs/PLAN.md). Your own tasks are in [docs/tasks/](docs/tasks/).

## Setup (Python 3.11)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On macOS, LightGBM also needs OpenMP: `brew install libomp`.

## Data

Raw data and processed data are never committed (`data/` is gitignored).

- Raw: CIC-IDS2017 MachineLearningCSV, saved to `data/raw/*.csv` (Member 1, M1.1).
- Processed: `data/processed/test.parquet`, shared via Google Drive: **[link to be added by Member 1]**

## Quick start without real models

Until Member 1's real models are in `models/`, you can generate fake models and fake test data that follow every contract:

```bash
python tests/make_fake_models.py
```

This writes `models/*` and `data/processed/test.parquet`. **Don't commit these fake files**, and don't run the script once the real models are in `models/`, because it overwrites them.

## Run the pipeline

```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1   # live demo, about 105 s
python -m pipeline.run --scenario scenarios/demo.json --speed 0   # as fast as possible
```

It writes to `data/events.db`, creating a fresh copy every run. The dashboard reads this file while the pipeline writes to it.

Scenarios:

| File | What it shows |
|---|---|
| `scenarios/demo.json` | Benign, then DoS, benign, PortScan, benign. Used for the live demo. |
| `scenarios/stress.json` | High rates, used for the latency numbers |
| `scenarios/slowscan.json` | Low-rate PortScan hidden in normal traffic (the known limitation) |

Other commands:

```bash
python -m pipeline.latency_report --scenario scenarios/stress.json   # writes reports/pipeline_latency.json
python -m pipeline.explainer                                         # sample explanations + IForest sign check
pytest tests/ -q                                                     # unit tests
```

## Run the dashboard

```bash
streamlit run dashboard/app.py
```

Open http://localhost:8501, then start the pipeline in a second terminal. The dashboard refreshes every second and copes with the DB being recreated, so you can start them in either order.

- **Live tab:** state badge, flows/s and packets/s, alerts in the last 60 s, a traffic chart (ELEVATED periods shaded red, z-score on the right axis), the last 50 alerts, and the explanation for one alert. Enter an alert ID from the table to inspect it, or leave it at 0 to follow the newest.
- **Sidebar:** detect/explain latency p50/p95, % of flows scored and explained per state, and the run summary once the run ends. **Pause live updates** freezes the view while you talk through an alert in the demo.
- **Results tab:** `reports/*.json` and `reports/figures/*.png`, with a "not available yet" note for anything missing. Reload the page after new reports land.

## Train the models

```bash
python ml/prepare.py
python ml/train.py
python ml/evaluate.py
```

(Member 1, in progress.)

## Status

Progress for every task is tracked in [docs/STATUS.md](docs/STATUS.md). Update your rows there when you push.
