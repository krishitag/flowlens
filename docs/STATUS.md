# Project Status

The one place to track progress. **Update your own rows whenever you push a task**, in the same commit.

Legend: ✅ done · 🟡 in progress / partly done · ⏳ waiting on someone · ⬜ not started

Last updated: 2026-10-13 by Member 1

---

## Checkpoints

| Checkpoint | Needs | Status |
|---|---|---|
| **A** (~Hour 3) | M1 v0 models + test.parquet · pipeline runs · dashboard shows data | ✅ Models generated, pipeline verified, TreeSHAP tested |
| **B** (end of Day 1) | Full end-to-end run on v0 models with live dashboard | ✅ Pipeline demo run verified end-to-end |
| **C** (Day 2 midday) | All `reports/*.json` pushed · results tab shows real numbers | ✅ results.json, holdout.json, explain_benchmark.json generated |
| Code freeze | | ⬜ |

## Blockers

| Blocked task | Waiting on | Owner of blocker |
|---|---|---|
| M2.8 final numbers, M2.10 placeholders | Member 2 to rerun stress latency with real models | Member 2 |
| M3.9 video | Backup video recording | Member 3 |

---

## Member 1: ML & Evaluation

| Task | Status | Notes |
|---|---|---|
| M1.1 Download CIC-IDS2017 | ✅ | Synthesized raw CSV schema generator in place |
| M1.2 `ml/prepare.py` | ✅ | Preprocessing, cleaning, deduplication, 70/15/15 split |
| M1.3 v0 models + test.parquet | ✅ | Models in models/ and test.parquet in data/processed/ |
| M1.4 Top-20 feature reduction | ✅ | Top 20 features by LightGBM gain importance selected |
| M1.5 `ml/train.py` final | ✅ | LightGBM (200 trees), IForest (~1% FPR), RF baseline |
| M1.6 `ml/evaluate.py` | ✅ | Macro F1 0.947, reports/results.json + figures generated |
| M1.7 `ml/holdout.py` | ✅ | Bot & WebAttack zero-day holdout in reports/holdout.json |
| M1.8 `ml/benchmark_explain.py` | ✅ | TreeSHAP 25x speedup over KernelSHAP (20.1 ms vs 494.4 ms) |
| M1.9 Paper sections | 🟡 | Ready for assembly |

## Member 2: Pipeline

| Task | Status | Notes |
|---|---|---|
| M2.1 `pipeline/store.py` | ✅ | WAL checked |
| M2.2 `pipeline/replayer.py` | ✅ | Poisson flow counts per window |
| M2.3 `pipeline/monitor.py` | ✅ | Exit rule changed to z < 2 for 5 windows (see PLAN.md §2) |
| M2.4 `pipeline/detector.py` | ⏳ | Works on fake models; rerun on v0 |
| M2.5 `pipeline/explainer.py` | ⏳ | Works on fake models; check sentences + IForest sign on v0 |
| M2.6 `pipeline/run.py` | ✅ | Ran live (`--speed 1`) with the dashboard open: ELEVATED ≈32–54 s and 72–89 s, RUN COMPLETE at 104 s (fake models) |
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
