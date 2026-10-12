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

(Member 3, in progress.)

## Train the models

```bash
python ml/prepare.py
python ml/train.py
python ml/evaluate.py
```

(Member 1, in progress.)

## Status

| Part | Owner | State |
|---|---|---|
| ML: data prep, models, evaluation | Member 1 | Not started in repo |
| Pipeline: replay, monitor, detect, explain, store | Member 2 | Code done and tested on fake models; waiting for real models |
| Dashboard, paper, slides | Member 3 | Not started in repo |
