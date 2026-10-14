# CLAUDE.md

Explainable real-time network anomaly detection (VIT Computer Networks project). Full plan: `docs/PLAN.md` — read it before doing anything.

## Folder ownership (do not edit outside your member's folders)
- Member 1 (ML): now handled by Member 2 (Krishita). `ml/`, `models/` and the ML reports may be edited in Member 2's sessions.
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

## Progress tracking (do this automatically, without being asked)
`docs/STATUS.md` is the team's progress tracker. Whenever you finish a task, partly finish one, or find a new blocker:
1. Update that task's row in `docs/STATUS.md`: the status emoji (✅ 🟡 ⏳ ⬜) and a short note.
2. Update the **Blockers** and **Checkpoints** tables if they're affected.
3. Set the "Last updated" line to today's date and the member's role.
4. Edit only the current member's rows, plus Blockers, Checkpoints and Shared. Never mark another member's task as done.
5. Tell the user you updated STATUS.md, so it goes into the same commit as the work.

Ask the user which member they are if it isn't clear. `docs/STATUS.md` is the one shared file every member may edit without team approval, and only for status updates.

## Git workflow
- `main` is protected. Work on a branch (`ml/<task>`, `pipeline/<task>`, `dashboard/<task>`), push it and open a PR. A PR needs 1 approval from another member before it can merge.
- Never push to `main` directly, and never force-push.
- Don't add `Co-authored-by: Claude` trailers or "Generated with Claude Code" lines to commits or PRs.
- Stage files by name. Never `git add .`, because the fake `models/*` files aren't gitignored.
- `tests/make_fake_models.py` writes fake `models/*` and `test.parquet` for development. Never commit them, and never run it once real models are in `models/`.

## Commands
- Setup: `pip install -r requirements.txt` (macOS: `brew install libomp` for LightGBM)
- Tests: `pytest tests/ -q`
- Pipeline: `python -m pipeline.run --scenario scenarios/demo.json --speed 1`
- Dashboard: `streamlit run dashboard/app.py` (from the repo root, so it picks up `.streamlit/config.toml`)
- Paper: `python paper/build.py` rebuilds `paper/paper.md` from `paper/sections/*` + `paper/pipeline_section.md`

## Status
Keep this updated at the end of every task.
- Data: real CIC-IDS2017 processed (`data/processed/{train,val,test}.parquet`, 76 features + label + dst_port). Test rows: BENIGN 45001, DoS 7500, DDoS 7500, PortScan 7500, BruteForce 1373, WebAttack 321, Bot 292.
- Models: trained on real data (`ml/train.py`, 20 features). Test macro F1 LightGBM 0.9719 (RF 0.9856), benign FPR 0.37%; WebAttack F1 0.86 is the weak class. IForest at 1% FPR: DoS recall 33%, others ~0% (kept by decision; limitation).
- Reports (real): `reports/results.json`, `holdout.json` (DoS held out: either 37.8%; Bot: 0%), `explain_benchmark.json` (TreeSHAP p50 2.4 ms vs Kernel SHAP ~2–2.6 s: ~800–1,100×, a range because Kernel SHAP varies by run), figures in `reports/figures/`.
- Pipeline (M2.1–M2.9): done, 23 tests pass, runs on real models. Per-window explanation cap (`--explain-cap`, default 300). Stress: e2e/window p95 223 ms (1,251 ms without the cap). Demo explains 99.7% of alerts. Slowscan never triggers ELEVATED (known limitation).
- Paper: `paper/pipeline_section.md` drafted, numbers are placeholders (fill from reports/).
- Still to do: share `test.parquet` via Drive, M1.9 + M2.10 paper sections, dashboard sidebar to ignore unexplained alerts (explain_ms = 0).
