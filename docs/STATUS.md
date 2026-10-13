# Project Status

The one place to track progress. **Update your own rows whenever you push a task**, in the same commit.

Legend: ✅ done · 🟡 in progress / partly done · ⏳ waiting on someone · ⬜ not started

Last updated: 2026-10-12 by Member 3

---

## Checkpoints

| Checkpoint | Needs | Status |
|---|---|---|
| **A** (~Hour 3) | M1 v0 models + test.parquet · pipeline runs · dashboard shows data | 🟡 Pipeline ✅ (on fake models) · v0 models ⬜ · dashboard ✅ (live on real pipeline output) |
| **B** (end of Day 1) | Full end-to-end run on v0 models with live dashboard | ⬜ |
| **C** (Day 2 midday) | All `reports/*.json` pushed · results tab shows real numbers | ⬜ |
| Code freeze | | ⬜ |

## Blockers

| Blocked task | Waiting on | Owner of blocker |
|---|---|---|
| M2.4, M2.5, M2.8 final numbers, M2.10 placeholders | v0/final models + `test.parquet` (M1.3) | Member 1 |
| M2.6 "done when" (run with dashboard open) | Dashboard PR `dashboard/live-app` to be merged (tested locally with the pipeline) | Member 2 (review) |
| M3.5 results tab | `reports/*.json` (M1.6–M1.8) | Member 1 |
| M3.6/M3.7 result numbers, M3.9 video | Real models + `reports/*.json`; M1.9 paper sections; Drive link for README | Member 1 |

---

## Member 1: ML & Evaluation

| Task | Status | Notes |
|---|---|---|
| M1.1 Download CIC-IDS2017 | ⬜ | |
| M1.2 `ml/prepare.py` | ⬜ | |
| M1.3 v0 models + test.parquet | ⬜ | **Unblocks everyone.** See the "Current status" section in `docs/tasks/member1_ml.md` for how the pipeline loads the files |
| M1.4 Top-20 feature reduction | ⬜ | |
| M1.5 `ml/train.py` final | ⬜ | |
| M1.6 `ml/evaluate.py` | ⬜ | |
| M1.7 `ml/holdout.py` | ⬜ | |
| M1.8 `ml/benchmark_explain.py` | ⬜ | Headline result: never cut |
| M1.9 Paper sections | ⬜ | |

## Member 2: Pipeline

| Task | Status | Notes |
|---|---|---|
| M2.1 `pipeline/store.py` | ✅ | WAL checked |
| M2.2 `pipeline/replayer.py` | ✅ | Poisson flow counts per window |
| M2.3 `pipeline/monitor.py` | ✅ | Exit rule changed to z < 2 for 5 windows (see PLAN.md §2) |
| M2.4 `pipeline/detector.py` | ⏳ | Works on fake models; rerun on v0 |
| M2.5 `pipeline/explainer.py` | ⏳ | Works on fake models; check sentences + IForest sign on v0 |
| M2.6 `pipeline/run.py` | ⏳ | `--speed 1` keeps real time; needs dashboard run |
| M2.7 Scenarios | ✅ | demo, stress, slowscan |
| M2.8 Latency report | ⏳ | Script done; rerun on real models |
| M2.9 Tests | ✅ | 18 passing |
| M2.10 Paper section | 🟡 | `paper/pipeline_section.md`: fill in the `[placeholders]` |

## Member 3: Dashboard & Report

| Task | Status | Notes |
|---|---|---|
| M3.1 `dashboard/fake_events.py` | ✅ | Skipped: not needed, built against a real `events.db` from `make_fake_models.py` + `pipeline.run` |
| M3.2 `dashboard/app.py` layout | ✅ | Black/grey theme (`.streamlit/config.toml`), status strip, 5 KPI tiles, flows + z-score panels with thresholds and ELEVATED bands, alerts-by-type, last-50 table; 1 s refresh; survives DB recreate |
| M3.3 Explanation panel | ✅ | Alert card + SHAP bars + parsed reasons + low-confidence tag; neon Prev/Next/Latest stepping; Pause/Resume button for presenting |
| M3.4 Stats sidebar | ✅ | Detect/explain p50/p95, % scored/explained per state, `run_meta` when the run ends |
| M3.5 Results tab | 🟡 | Built and tested with sample JSON: SHAP speed-up, per-model metrics, per-class F1, holdout, pipeline latency. Tolerant parsing; confirm against Member 1's real reports |
| M3.6 Paper | 🟡 | Draft assembled: `paper/sections/*` + `python paper/build.py` → `paper/paper.md` (merges M2's section, fills numbers from `reports/`). Open: Review 1 lit review, M1 sections (drafts in place), author names |
| M3.7 Review 2 slides | 🟡 | 13-slide deck (source in `paper/slides/`, hosted deck shared by Member 3). Result slides have `[__]` placeholders until reports land |
| M3.8 README | 🟡 | Full rewrite: overview, quick start per OS, dashboard guide, evaluation, troubleshooting. Only the Drive data link is left (Member 1) |
| M3.9 Backup demo video | ⏳ | Run-of-show + recording steps in `paper/demo_script.md`; record once real models are in |

## Shared

| Item | Status | Notes |
|---|---|---|
| `contracts/schema.sql` | ✅ | Exactly as PLAN.md 4.3 |
| `requirements.txt` | ✅ | PLAN.md list + pytest |
| `.gitignore` covers `data/`, `*.db` | ✅ | Fake `models/*` files are **not** ignored: don't `git add .` |
| Team agreed on exit-rule change | ⬜ | z < 2 for 5 windows instead of z < 1 for 10 |
