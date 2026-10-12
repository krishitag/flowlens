# CLAUDE.md

Explainable real-time network anomaly detection (VIT Computer Networks project). Full plan: `docs/PLAN.md` — read it before doing anything.

## Folder ownership (do not edit outside your member's folders)
- Member 1 (ML): `ml/`, `models/`, `reports/results.json`, `reports/holdout.json`, `reports/explain_benchmark.json`, `reports/figures/`
- Member 2 (pipeline): `pipeline/`, `scenarios/`, `tests/`, `reports/pipeline_latency.json`
- Member 3 (dashboard/report): `dashboard/`, `paper/`, `README.md`
- Shared (change only if the user explicitly says the team agreed): `contracts/`, `requirements.txt`, `CLAUDE.md`, `docs/`

## Frozen contracts (see docs/PLAN.md Section 4)
- Model artifacts: `models/lgbm.joblib`, `models/iforest.joblib`, `models/features.json` (ordered feature list), `models/labels.json`, `models/iforest_threshold.json`, `models/baselines.json` (101 benign percentiles + 99.9th per feature)
- Data: `data/processed/test.parquet` = feature columns + `label` + `dst_port`
- Classes: BENIGN, DoS, DDoS, PortScan, BruteForce, WebAttack, Bot
- Events DB: `data/events.db`, schema in `contracts/schema.sql` (tables `traffic_windows`, `alerts`, `run_meta`), WAL mode
- Scenario JSON format: PLAN.md 4.4

Never rename columns, tables, files or JSON keys from these contracts. If a task seems to need a contract change, stop and tell the user.

## Rules
- Python 3.11. Deps only from `requirements.txt` unless the user approves adding one.
- Never use `Destination Port`, IPs, Flow ID or timestamps as model features.
- Explanations: `shap.TreeExplainer`, built once at startup. KernelExplainer only in `ml/benchmark_explain.py`.
- Never commit anything under `data/`.
- Keep code simple and readable; this is a 2-day university project, not production.
- After implementing a task, tell the user the exact command to verify its "done when" condition from PLAN.md.
- `tests/make_fake_models.py` writes fake `models/*` and `test.parquet` for development. Never commit them, and never run it once real models are in `models/`.

## Commands
- Setup: `pip install -r requirements.txt` (macOS: `brew install libomp` for LightGBM)
- Tests: `pytest tests/ -q`
- Pipeline: `python -m pipeline.run --scenario scenarios/demo.json --speed 1`
- Dashboard: `streamlit run dashboard/app.py`
