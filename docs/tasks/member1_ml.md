# Member 1: ML & Evaluation

You build the models and produce the numbers that prove the project's main claim. Everyone else depends on your files, so **push early (v0 models within ~3 hours of starting) and improve them later.**

Source of truth: [docs/PLAN.md](../PLAN.md). If this file and the plan disagree, follow the plan.

---

## What you own

| You edit | You never edit |
|---|---|
| `ml/`, `models/`, `reports/results.json`, `reports/holdout.json`, `reports/explain_benchmark.json`, `reports/figures/` | `pipeline/`, `scenarios/`, `tests/`, `dashboard/`, `paper/`, `README.md`, and the shared files (`contracts/`, `requirements.txt`, `CLAUDE.md`, `docs/`) unless all 3 of you agree |

Branch prefix: `ml/` (for example `ml/prepare-data`). Commit messages start with `[ml]`.

## Who uses your files

- **Member 2** loads everything in `models/` and replays `data/processed/test.parquet` as live traffic.
- **Member 3** shows `reports/*.json` and `reports/figures/` in the dashboard's Results tab and uses them in the paper.

If you change a file name, column name or JSON key, their code breaks. These are **frozen contracts** (PLAN.md Section 4).

## Current status: the pipeline is waiting on your files

Member 2's pipeline is finished and has been tested on fake models. As soon as your v0 files are in `models/` and `data/processed/`, it runs on them. Here is exactly how it uses them:

- **`lgbm.joblib`** must be an `LGBMClassifier` (the sklearn API), because the pipeline calls `predict_proba()` and `shap.TreeExplainer` on it. Train on integer class ids 0–6 that match `labels.json`.
- **`iforest.joblib`** must be a sklearn `IsolationForest`. The flag rule is **`iforest.score_samples(X) < threshold`**, so set `iforest_threshold.json` from **`score_samples`**, not `decision_function`. They differ by an offset.
- **Feature columns:** the pipeline selects `test.parquet[features.json]` by name, so the names in `features.json` must match the parquet's column names exactly.
- **`baselines.json`** must have exactly 102 numbers per feature.
- **Expected format:** [tests/make_fake_models.py](../../tests/make_fake_models.py) writes every file in the correct format with synthetic data. Copy its structure.
- **Testing your v0 files** after you push them:
  ```
  python -m pipeline.explainer                                     # correlation should be strongly positive
  python -m pipeline.run --scenario scenarios/demo.json --speed 0
  ```
  Also tell Member 2 when they're in.
- **Setup:** `pip install -r requirements.txt`. On macOS, also run `brew install libomp`.

## Files you must produce (contract 4.1)

| Path | What's in it |
|---|---|
| `models/lgbm.joblib` | trained LightGBM multiclass model |
| `models/iforest.joblib` | IsolationForest trained on **BENIGN train flows only** |
| `models/rf.joblib` | RandomForest baseline (skip committing it if it's over 50 MB) |
| `models/features.json` | ordered list of feature names the models expect |
| `models/labels.json` | `{"0": "BENIGN", "1": "DoS", ...}` |
| `models/iforest_threshold.json` | `{"threshold": <float>}`. A score below this counts as anomalous. Set it for ~1% false positives on benign validation flows. |
| `models/baselines.json` | `{feature: [q0, q1, ..., q100, q99_9]}`: 101 percentiles of BENIGN train flows, plus the 99.9th as the last element |
| `data/processed/test.parquet` | every `features.json` column + `label` (grouped class) + `dst_port`. **Share it via Google Drive, never commit it.** |
| `data/processed/holdout_<class>.parquet` | flows of the held-out attack class |

**Classes (contract 4.2):** `BENIGN`, `DoS` (Hulk, GoldenEye, slowloris, Slowhttptest), `DDoS`, `PortScan`, `BruteForce` (FTP-Patator, SSH-Patator), `WebAttack` (all three Web Attack labels), `Bot`. **Drop** Infiltration and Heartbleed.

---

## Tasks

### M1.1: Download the dataset (start in the first 10 minutes)
- Get **CIC-IDS2017 MachineLearningCSV** (also called MachineLearningCVE) from the UNB CIC site (you fill in a form first) or a Kaggle mirror.
- Put the CSVs in `data/raw/`. There's one CSV per capture day, with ~78 flow features and a `Label` column.
- **Done when:** the CSVs are on disk. Check with `ls data/raw/*.csv`.

### M1.2: `ml/prepare.py`
Steps, in order:
1. Load all the CSVs and strip whitespace from the column names (the raw files have leading spaces).
2. Drop the duplicate column (`Fwd Header Length` appears twice).
3. Replace ±inf with NaN, then drop those rows.
4. Drop exact duplicate rows.
5. Group the labels as in contract 4.2 and drop Infiltration and Heartbleed.
6. Rename `Destination Port` to `dst_port`. Keep it in the data, but **never use it as a feature** (it leaks the answer).
7. Sample: cap each attack class at 50k rows and BENIGN at 300k.
8. Split stratified 70/15/15 into train, val and test.
9. Save `data/processed/{train,val,test}.parquet` and print the class counts.
- **Done when:** `python ml/prepare.py` runs end to end and prints class counts.

### M1.3: v0 quick model (push within ~3 hours, Checkpoint A)
- LightGBM on all features, default params, `class_weight='balanced'`.
- IsolationForest on BENIGN train flows only.
- Write **every** file in the table above, even if the numbers are rough.
- Upload `test.parquet` to Drive and send the link to Member 2.
- **Done when:** Member 2 can load the models and predict. A quick check: `python -c "import joblib; m=joblib.load('models/lgbm.joblib'); print(m)"`.

### M1.4: Feature reduction
- Take the top 20 features by LightGBM **gain** importance and retrain on only those.
- Use the 20-feature version as final: it's faster and its explanations are easier to read.
- Update `features.json` and `baselines.json` to match.
- **Done when:** macro F1 is within ~1–2 points of the all-feature model.

### M1.5: `ml/train.py` (final)
- LightGBM with ~200 trees.
- IsolationForest with 100 trees, threshold set for ~1% FPR on benign validation flows.
- RandomForest baseline with 100 trees and `n_jobs=-1`.
- **Done when:** `python ml/train.py` rebuilds all of `models/*` in one command.

### M1.6: `ml/evaluate.py`
- For LightGBM and RF: per-class precision, recall and F1, macro F1, benign false positive rate, confusion matrix.
- Per-flow inference latency.
- Outputs: `reports/results.json`, `reports/figures/confusion_lgbm.png`, `reports/figures/per_class_f1.png`.
- **Done when:** the numbers are in the JSON. Check with `python ml/evaluate.py && cat reports/results.json`.

### M1.7: `ml/holdout.py` (leave-one-attack-out)
- Retrain LightGBM **without** one attack class. Do `Bot` first, then `WebAttack` if there's time.
- On that class's flows, report recall for LightGBM alone, IsolationForest alone, and either one.
- Outputs: `reports/holdout.json`, `data/processed/holdout_<class>.parquet`.
- **Done when:** the table is ready for the paper.

### M1.8: `ml/benchmark_explain.py` (the headline result: never cut this)
- On 200 flagged test flows, time **TreeSHAP** per flow.
- Time **Kernel SHAP** per flow on only 50 flows, with a background of 100 benign samples. Kernel SHAP is slow, which is exactly the point being measured.
- Report the mean, p50 and p95 for each.
- Outputs: `reports/explain_benchmark.json`, `reports/figures/shap_latency.png`.
- This is the **only** place in the repo where `KernelExplainer` is allowed.
- **Done when:** the JSON and figure exist.

### M1.9: Paper sections
- Write **Dataset & Preprocessing**, **Models** and **Evaluation results**, and send the text to Member 3.

---

## Timeline

| When | You |
|---|---|
| Hour 0–1 | Agree on the contracts with the team, **start the download** |
| Hour 1–3 | M1.2 |
| **Checkpoint A (~Hour 3)** | **Push v0 models + share test.parquet** (M1.3) |
| Hour 3–7 | M1.4, M1.5 |
| **Checkpoint B (end of Day 1)** | Full end-to-end run with the team |
| Day 2 morning | M1.6, M1.7, M1.8 |
| **Checkpoint C (midday)** | All your `reports/*.json` pushed |
| Day 2 afternoon | M1.9 |

If you're behind, cut in this order: RF baseline, then the second holdout class. **Never cut M1.8.**

## Watch out for
- **Leakage:** `Destination Port`, IPs, Flow ID and timestamps must never be features.
- **Too-good accuracy:** over 99.5% macro F1 usually means leakage or duplicate rows shared across splits. Deduplicate *before* splitting.
- **Large files:** never commit CSVs, parquet files or anything under `data/`.
- **Feature order:** `features.json` order must match the column order the model was trained on.

## Starter prompt for Claude Code
> I'm Member 1. Read docs/PLAN.md and CLAUDE.md. Implement task M1.2 in ml/prepare.py following contracts 4.1 and 4.2. Don't modify files outside ml/, models/ and reports/.

Do one task ID per prompt, run what it writes, check the "done when" condition, then commit.
