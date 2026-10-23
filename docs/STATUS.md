# Project Status

The one place to track progress. **Update your own rows whenever you push a task**, in the same commit.

Legend: ✅ done · 🟡 in progress / partly done · ⏳ waiting on someone · ⬜ not started

Last updated: 2026-10-24 by Member 2

---

## Checkpoints

| Checkpoint | Needs | Status |
|---|---|---|
| **A** (~Hour 3) | M1 v0 models + test.parquet · pipeline runs · dashboard shows data | ✅ Real models + `test.parquet` on `main` (`git pull`) · pipeline runs on them · dashboard ✅ |
| **B** (end of Day 1) | Full end-to-end run on v0 models with live dashboard | ✅ `pipeline.run` demo works end to end on real models (ELEVATED during DoS + PortScan) |
| **C** (Day 2 midday) | All `reports/*.json` pushed · results tab shows real numbers | ✅ All `reports/*.json` + figures on `main` from real models · results tab confirmed by Member 3 |
| Code freeze | | ⬜ |

## Blockers

| Blocked task | Waiting on | Owner of blocker |
|---|---|---|
| M3.5 results tab | Nothing: real `reports/*.json` are on `main` | — |
| M3.6/M3.7 result numbers, M3.9 video | Nothing from Member 2 left: models, reports, M1.9 sections on `main`. README: no Drive link needed, `test.parquet` comes with `git pull` | — |
| README, `07_results.md`, slides, REVIEW3 numbers | Models retrained with `max_bin=1023` (`ml/lgbm-max-bin`): macro F1 0.972 → 0.987, WebAttack F1 0.86 → 0.96, FPR 0.37% → 0.18%, DoS holdout either 37.8% → 51.6%. Hard-coded old numbers need updating | Member 3 (README, `07_results.md`, slides) |

---

## Member 1: ML & Evaluation

Member 1 wrote the first version of the ML scripts (PR #2) and worked on the paper and slides with Member 3. The M1 tasks were finished by Member 2 and are tracked in Member 2's table below.

## Member 2: Pipeline + ML & Evaluation

| Task | Status | Notes |
|---|---|---|
| M2.1 `pipeline/store.py` | ✅ | WAL checked |
| M2.2 `pipeline/replayer.py` | ✅ | Poisson flow counts per window |
| M2.3 `pipeline/monitor.py` | ✅ | Exit rule changed to z < 2 for 5 windows (see PLAN.md §2) |
| M2.4 `pipeline/detector.py` | ✅ | Runs on real models (demo: detect p50 0.02 ms) |
| M2.5 `pipeline/explainer.py` | ✅ | Real models: IForest SHAP vs score corr 0.995, sentences sensible, explain p50 0.56 ms |
| M2.6 `pipeline/run.py` | ✅ | `--explain-cap` (default 300, most confident first). Demo: ELEVATED 32–53 s and 72–88 s, 6,538 alerts, 6,521 explained (99.7%); slowscan: never ELEVATED, 15 PortScan alerts (10% sampling) + 2 benign FPs |
| M2.7 Scenarios | ✅ | demo, stress, slowscan |
| M2.8 Latency report | ✅ | Stress, real models, explain cap 300: detect p50 0.013 ms, explain p50 0.46 ms, e2e/window p50 166 ms, p95 186 ms (186–225 over 3 runs; 976–1,245 ms without the cap). ELEVATED: 100% scored, 18% explained |
| M2.9 Tests | ✅ | 23 passing (incl. `tests/test_explain_cap.py`) |
| M2.10 Paper section | ✅ | `paper/pipeline_section.md`: all placeholders filled from real models; new subsection on the 300 explanation cap (stress p95 976–1,245 → 186–225 ms); numbers updated for `max_bin=1023` models; slow-scan rechecked |
| M1.1 Download CIC-IDS2017 | ✅ | |
| M1.2 `ml/prepare.py` | ✅ | train 324k / val 69k / test 69k rows, 76 features |
| M1.3 v0 models + test.parquet | ✅ | Real models on `main`, `pipeline.explainer` check passes (corr 0.995). `data/processed/test.parquet` committed (the one file under `data/` in git), so no Drive link |
| M1.4 Top-20 feature reduction | ✅ | `max_bin=1023`: val macro F1 0.9894 (76) → 0.9871 (20), −0.2 pts. One feature changed: `Fwd IAT Max` replaces `Fwd Packet Length Std` |
| M1.5 `ml/train.py` final | ✅ | One command, ~30 s. rf.joblib 27 MB. `max_bin=1023` fixed WebAttack (default 255 bins too coarse; class weights, trees, leaves made no difference). IForest kept at 1% FPR by decision: catches 48% of held-out DoS, ~0% of other attacks (a limitation for the paper) |
| M1.6 `ml/evaluate.py` | ✅ | Test macro F1 LightGBM 0.9866 / RF 0.9864; benign FPR 0.18% / 0.15%; accuracy 99.84%; WebAttack F1 0.96, Bot 0.95 |
| M1.7 `ml/holdout.py` | ✅ | DoS and Bot. Recall LGBM/IForest/either: DoS 4.4/47.8/51.6%, Bot 0/0/0% |
| M1.8 `ml/benchmark_explain.py` | ✅ | TreeSHAP p50 2.3 ms vs Kernel SHAP ~1.9–2.6 s per flow: ~800–1,100× at the median (latest rerun 844–990×) (range over 3 Kernel SHAP rounds; it varies run to run) |
| M1.9 Paper sections | ✅ | `paper/sections/03_dataset.md` and `04_models.md` rewritten with real numbers. Results sentences + fixes for `07_results.md` sent to Member 3 |

## Member 3: Dashboard & Report

| Task | Status | Notes |
|---|---|---|
| M3.1 `dashboard/fake_events.py` | ✅ | Skipped: not needed, built against a real `events.db` from `make_fake_models.py` + `pipeline.run` |
| M3.2 `dashboard/app.py` layout | ✅ | Black/grey theme (`.streamlit/config.toml`), status strip, 5 KPI tiles, flows + z-score panels with thresholds and ELEVATED bands, alerts-by-type, last-50 table; 1 s refresh; survives DB recreate |
| M3.3 Explanation panel | ✅ | Alert card + SHAP bars + parsed reasons + low-confidence tag; neon Prev/Next/Latest stepping; Pause/Resume button for presenting |
| M3.4 Stats sidebar | ✅ | Detect/explain p50/p95 (explain over `explain_ms > 0` only, with a count of cap-skipped alerts), % scored/explained per state, `run_meta` when the run ends |
| M3.5 Results tab | ✅ | Confirmed on the real `reports/*.json`: speed-up shown as the 800–1,100× range, per-model metrics, per-class F1, DoS/Bot holdout, pipeline latency, figures |
| M3.6 Paper | ✅ | Final: `python paper/build.py` → `paper/paper.md`, all numbers from `reports/`. Results text, holdout definition and speed-up range per Member 2's notes. Related work written from references [7]–[11] (Review 1 lit review wasn't available). Shareable doc version for export to Word/PDF |
| M3.7 Review 2 slides | ✅ | 13 slides with final numbers (source `paper/slides/`, hosted deck downloads as PPTX/PDF). Explanation slide uses a real PortScan alert from the demo |
| M3.8 README | ✅ | Rewritten on `main` (#11, #12): no Drive link needed, retraining steps included |
| M3.9 Backup demo video | ⬜ | Unblocked: real models are on `main`. Record with `paper/demo_script.md` (run-of-show + recording steps) |

## Shared

| Item | Status | Notes |
|---|---|---|
| `contracts/schema.sql` | ✅ | Exactly as PLAN.md 4.3 |
| `requirements.txt` | ✅ | PLAN.md list + pytest + matplotlib (for `ml/` figures) |
| `.gitignore` covers `data/`, `*.db` | ✅ | Exception: `data/processed/test.parquet` is tracked (force-added). Don't run `make_fake_models.py`, it would overwrite it. Don't `git add .` |
| Team agreed on exit-rule change | ⬜ | z < 2 for 5 windows instead of z < 1 for 10 |
