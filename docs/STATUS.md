# Project Status

The one place to track progress. **Update your own rows whenever you push a task**, in the same commit.

Legend: ✅ done · 🟡 in progress / partly done · ⏳ waiting on someone · ⬜ not started

Last updated: 2026-10-12 by Member 3

---

## Checkpoints

| Checkpoint | Needs | Status |
|---|---|---|
| **A** (~Hour 3) | M1 v0 models + test.parquet · pipeline runs · dashboard shows data | 🟡 Pipeline ✅ (on fake models) · v0 models ⬜ · dashboard ✅ (live on real pipeline output, PR open) |
| **B** (end of Day 1) | Full end-to-end run on v0 models with live dashboard | ⬜ |
| **C** (Day 2 midday) | All `reports/*.json` pushed · results tab shows real numbers | ⬜ |
| Code freeze | | ⬜ |

## Blockers

| Blocked task | Waiting on | Owner of blocker |
|---|---|---|
| M2.4, M2.5, M2.8 final numbers, M2.10 placeholders | v0/final models + `test.parquet` (M1.3) | Member 1 |
| M2.6 "done when" (run with dashboard open) | Dashboard PR `dashboard/live-app` to be merged (tested locally with the pipeline) | Member 2 (review) |
| M3.5 results tab | `reports/*.json` (M1.6–M1.8) | Member 1 |

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
| M3.2 `dashboard/app.py` layout | ✅ | State badge, metrics, flows/z-score chart with ELEVATED shading, last-50 alert table; 1 s refresh; survives DB recreate |
| M3.3 Explanation panel | ✅ | Pick by alert ID (0 = latest); SHAP bar chart + sentences + low-confidence tag. "Pause live updates" toggle for the demo |
| M3.4 Stats sidebar | ✅ | Detect/explain p50/p95, % scored/explained per state, `run_meta` when the run ends |
| M3.5 Results tab | 🟡 | Tab built; shows `pipeline_latency.json` properly. M1 reports render generically (tables/JSON) until their formats are known. Waiting on M1.6–M1.8 |
| M3.6 Paper | ⬜ | Member 2's section is in `paper/` |
| M3.7 Review 2 slides | ⬜ | |
| M3.8 README | 🟡 | Setup, pipeline and dashboard sections written; data link + training sections need Member 1 |
| M3.9 Backup demo video | ⬜ | |

## Shared

| Item | Status | Notes |
|---|---|---|
| `contracts/schema.sql` | ✅ | Exactly as PLAN.md 4.3 |
| `requirements.txt` | ✅ | PLAN.md list + pytest |
| `.gitignore` covers `data/`, `*.db` | ✅ | Fake `models/*` files are **not** ignored: don't `git add .` |
| Team agreed on exit-rule change | ⬜ | z < 2 for 5 windows instead of z < 1 for 10 |
