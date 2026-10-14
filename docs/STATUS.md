# Project Status

The one place to track progress. **Update your own rows whenever you push a task**, in the same commit.

Legend: ✅ done · 🟡 in progress / partly done · ⏳ waiting on someone · ⬜ not started

Last updated: 2026-10-15 by Member 2 (also handling ML)

---

## Checkpoints

| Checkpoint | Needs | Status |
|---|---|---|
| **A** (~Hour 3) | M1 v0 models + test.parquet · pipeline runs · dashboard shows data | ✅ Real models + `test.parquet` on `main` (`git pull`) · pipeline runs on them · dashboard ✅ |
| **B** (end of Day 1) | Full end-to-end run on v0 models with live dashboard | ✅ `pipeline.run` demo works end to end on real models (ELEVATED during DoS + PortScan) |
| **C** (Day 2 midday) | All `reports/*.json` pushed · results tab shows real numbers | 🟡 All `reports/*.json` + figures on `main` from real models · Member 3 to confirm the results tab |
| Code freeze | | ⬜ |

## Blockers

| Blocked task | Waiting on | Owner of blocker |
|---|---|---|
| M3.4 sidebar explain p50/p95 | With the explanation cap, unexplained alerts have `explain_ms = 0`; the sidebar should use `WHERE explain_ms > 0` (rare in demo: 17 of 6,550) | Member 3 |
| M1.7 holdout story | Held-out Bot: 0% caught by anything; held-out DoS: either 37.8%. IForest kept at 1% FPR by decision: write up as a limitation | Member 2 |
| M3.5 results tab | Nothing: real `reports/*.json` are on `main` | — |
| M3.6/M3.7 result numbers, M3.9 video | Nothing from Member 2 left: models, reports, M1.9 sections on `main`. README: no Drive link needed, `test.parquet` comes with `git pull` | — |

---

## Member 1: ML & Evaluation (now handled by Member 2)

| Task | Status | Notes |
|---|---|---|
| M1.1 Download CIC-IDS2017 | ✅ | |
| M1.2 `ml/prepare.py` | ✅ | train 324k / val 69k / test 69k rows, 76 features |
| M1.3 v0 models + test.parquet | ✅ | Real models on `main`, `pipeline.explainer` check passes (corr 0.995). `data/processed/test.parquet` committed (the one file under `data/` in git), so no Drive link |
| M1.4 Top-20 feature reduction | ✅ | Val macro F1 0.9901 (76) → 0.9721 (20), −1.8 pts; WebAttack F1 drops most (0.86) |
| M1.5 `ml/train.py` final | ✅ | One command, ~30 s. rf.joblib 27 MB. IForest recall on attacks is very low (see Blockers) |
| M1.6 `ml/evaluate.py` | ✅ | Test macro F1 LightGBM 0.9719 / RF 0.9856; benign FPR 0.37% / 0.14% |
| M1.7 `ml/holdout.py` | ✅ | DoS and Bot. Recall LGBM/IForest/either: DoS 4.9/33.0/37.8%, Bot 0/0/0% |
| M1.8 `ml/benchmark_explain.py` | ✅ | TreeSHAP p50 2.4 ms vs Kernel SHAP ~1.9–2.6 s per flow: ~800–1,100× at the median (range over 3 Kernel SHAP rounds; it varies run to run) |
| M1.9 Paper sections | ✅ | `paper/sections/03_dataset.md` and `04_models.md` rewritten with real numbers. Results sentences + fixes for `07_results.md` sent to Member 3 |

## Member 2: Pipeline

| Task | Status | Notes |
|---|---|---|
| M2.1 `pipeline/store.py` | ✅ | WAL checked |
| M2.2 `pipeline/replayer.py` | ✅ | Poisson flow counts per window |
| M2.3 `pipeline/monitor.py` | ✅ | Exit rule changed to z < 2 for 5 windows (see PLAN.md §2) |
| M2.4 `pipeline/detector.py` | ✅ | Runs on real models (demo: detect p50 0.02 ms) |
| M2.5 `pipeline/explainer.py` | ✅ | Real models: IForest SHAP vs score corr 0.995, sentences sensible, explain p50 0.56 ms |
| M2.6 `pipeline/run.py` | ✅ | `--explain-cap` (default 300, most confident first). Demo: ELEVATED 32–53 s and 72–88 s, 6,550 alerts, 6,533 explained (99.7%); slowscan: never ELEVATED, 15 PortScan alerts (10% sampling) + 2 benign FPs |
| M2.7 Scenarios | ✅ | demo, stress, slowscan |
| M2.8 Latency report | ✅ | Stress, real models, explain cap 300: detect p50 0.014 ms, explain p50 0.54 ms, e2e/window p50 194 ms, p95 223 ms (was 1,251 ms without the cap). ELEVATED: 100% scored, 18% explained |
| M2.9 Tests | ✅ | 23 passing (incl. `tests/test_explain_cap.py`) |
| M2.10 Paper section | ✅ | `paper/pipeline_section.md`: all placeholders filled from real models; new subsection on the 300 explanation cap (stress p95 1,251 → 223 ms); slow-scan rechecked |

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
| `.gitignore` covers `data/`, `*.db` | ✅ | Exception: `data/processed/test.parquet` is tracked (force-added). Don't run `make_fake_models.py`, it would overwrite it. Don't `git add .` |
| Team agreed on exit-rule change | ⬜ | z < 2 for 5 windows instead of z < 1 for 10 |
