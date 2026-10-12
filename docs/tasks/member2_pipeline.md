# Member 2: Streaming Pipeline & Explanations (backend)

You build the engine that replays traffic as if it were live, detects attacks, explains them, and writes everything to a database the dashboard reads. **Never wait on anyone:** use a fake parquet file and a stub detector until Member 1's models arrive.

Source of truth: [docs/PLAN.md](../PLAN.md). If this file and the plan disagree, follow the plan.

---

## What you own

| You edit | You never edit |
|---|---|
| `pipeline/`, `scenarios/`, `tests/`, `reports/pipeline_latency.json` | `ml/`, `models/`, `dashboard/`, `paper/`, `README.md`, and the shared files (`contracts/`, `requirements.txt`, `CLAUDE.md`, `docs/`) unless all 3 of you agree |

Branch prefix: `pipeline/` (for example `pipeline/explainer`). Commit messages start with `[pipeline]`.

## How your pieces fit

```
scenario.json ─▶ replayer ─▶ monitor (Tier 1) ─▶ detector (Tier 2) ─▶ explainer ─▶ store (SQLite) ─▶ dashboard
```

- **Input from Member 1:** `models/*` and `data/processed/test.parquet` (shared via Drive).
- **Output to Member 3:** rows in `data/events.db`, which their dashboard reads live.

## Contracts you must follow exactly (PLAN.md Section 4)

**Model files you load** (from Member 1): `models/lgbm.joblib`, `models/iforest.joblib`, `models/features.json` (ordered feature list), `models/labels.json`, `models/iforest_threshold.json` (`{"threshold": x}`, a score **below** x counts as anomalous), `models/baselines.json` (`{feature: [101 percentiles q0..q100, q99_9]}`).

**Test data:** `data/processed/test.parquet` = the feature columns + `label` + `dst_port`.

**Database:** `data/events.db`, created from `contracts/schema.sql` in WAL mode. It has 3 tables:
- `traffic_windows` (one row per 1-second window): `ts, flows, packets, bytes, z_score, state, scored, explained`
- `alerts` (one row per flagged flow): `ts, flow_idx, dst_port, true_label, pred_label, pred_prob, if_score, source, top_features, explanation, detect_ms, explain_ms`
- `run_meta`: `key, value`

`top_features` is a JSON string: `[{"name", "value", "contribution", "percentile"}]`.

**Scenario format (4.4):**
```json
{
  "window_s": 1,
  "segments": [
    {"label": "BENIGN", "rate": 40,  "duration": 30},
    {"label": "DoS",    "rate": 400, "duration": 20, "benign_mix": 0.3}
  ]
}
```
`rate` = flows per simulated second, sampled from `test.parquet` rows with that label. `benign_mix` = the fraction of BENIGN flows mixed into an attack segment.

---

## Tasks

### M2.1: `pipeline/store.py`
- Create the DB from `contracts/schema.sql` (it sets WAL mode, so the dashboard can read while you write).
- Helpers: `insert_window()`, `insert_alerts(batch)`, `set_meta()`.
- Insert in **one batch per window**, not one row at a time.
- **Done when:** the dashboard can read while the pipeline writes.

### M2.2: `pipeline/replayer.py`
- Read the scenario JSON and `test.parquet`.
- Yield `(ts, window_flows_df)` for each window, sampling rows for each segment's label with `benign_mix`.
- Add a `--speed` multiplier: 1 = real time, 0 = as fast as possible.
- Before Member 1's parquet arrives, build a **tiny fake parquet** with the same columns.
- **Done when:** it prints per-window counts for the demo scenario.

### M2.3: `pipeline/monitor.py` (Tier 1)
- For each 1-second window, compute flows/s and packets/s.
- Keep an EWMA mean and variance with alpha = 0.1, and compute a z-score.
- **NORMAL → ELEVATED:** z > 3 for **3 consecutive** windows.
- **ELEVATED → NORMAL:** z < 1 for **10 consecutive** windows.
- Write it as a pure function or class so it's easy to unit test.
- **Done when:** the state flips to ELEVATED during the DoS segment.

### M2.4: `pipeline/detector.py` (Tier 2)
- Load `models/*` once.
- **NORMAL:** score a random 10% of flows with LightGBM.
- **ELEVATED:** score **every** flow with LightGBM **and** IsolationForest.
- **Flag rule:** flagged if LightGBM predicts non-BENIGN with prob ≥ 0.5, **or** the IsolationForest score is below its threshold. Record `source` as `lgbm`, `iforest` or `both`.
- `detect_ms` per flow = batch time / batch size.
- **Before M1.3 lands, use a stub that flags randomly**, so you're never blocked.
- **Done when:** it works with the v0 models.

### M2.5: `pipeline/explainer.py`
- Build `shap.TreeExplainer` **once at startup**, one for LightGBM and one for IsolationForest. Never use KernelExplainer here.
- For each flagged flow:
  1. Take the SHAP contributions for the **predicted class**. If only IsolationForest flagged it, use the IsolationForest explainer.
  2. Take the top 3 features pushing toward "anomalous".
  3. Find each value's percentile in `baselines.json` with `np.searchsorted`.
  4. Turn it into a sentence, e.g. `Flow Packets/s = 4,812 (above 99.9% of normal flows)`.
- Time `explain_ms` per flow.
- **Done when:** the sentences read sensibly.

### M2.6: `pipeline/run.py`
- Wire everything together. The CLI:
  ```
  python -m pipeline.run --scenario scenarios/demo.json --speed 1
  ```
- Write windows + alerts every window, and a run summary to `run_meta` at the end.
- **Done when:** it runs end to end with the dashboard open.

### M2.7: Scenarios in `scenarios/`
- `demo.json`: ~2 minutes, for the live demo.
- `stress.json`: high rate, run with `--speed 0`, used for the latency numbers.
- `slowscan.json`: low-rate PortScan, to show the known limitation honestly.
- **Done when:** all three run.

### M2.8: Latency report
- From a `stress.json` run: p50/p95 of `detect_ms`, `explain_ms` and end-to-end time per window, plus the % of flows scored and explained in NORMAL vs ELEVATED.
- Output: `reports/pipeline_latency.json`.
- **Done when:** the numbers are ready for the paper.

### M2.9: Minimal tests
- `tests/test_monitor.py`: state transitions (NORMAL → ELEVATED after 3 high windows, back after 10 low ones).
- `tests/test_explainer.py`: the percentile lookup and sentence formatting.
- **Done when:** `pytest` is green.

### M2.10: Paper sections
- Write **System Architecture**, **Two-Tier Design**, **Explanation Generation** and **Latency results**, and send the text to Member 3.

---

## Timeline

| When | You |
|---|---|
| Hour 0–1 | Agree on the contracts with the team |
| Hour 1–3 | M2.1–M2.3 (using a tiny fake parquet) |
| **Checkpoint A (~Hour 3)** | Pipeline runs with the stub detector |
| Hour 3–7 | M2.4–M2.6 against Member 1's v0 models |
| **Checkpoint B (end of Day 1)** | Full end-to-end run: replay → detect → explain → live dashboard |
| Day 2 morning | M2.7–M2.9, swap in the final models |
| **Checkpoint C (midday)** | `pipeline_latency.json` pushed |
| Day 2 afternoon | M2.10 |

If you're behind, cut `slowscan.json` first.

## Watch out for
- Build the SHAP explainers **once**, not per flow. Rebuilding them per flow wrecks your latency numbers.
- Read feature order from `features.json`. Never hardcode it, because Member 1 changes it in M1.4.
- Don't rename DB columns or tables. Member 3's dashboard is built against the exact schema.
- Never commit `data/events.db` or anything under `data/`.

## Starter prompt for Claude Code
> I'm Member 2. Read docs/PLAN.md and CLAUDE.md. Implement task M2.5 in pipeline/explainer.py following contract 4.1 and the explainer description in Section 2. Don't modify files outside pipeline/ and tests/.

Do one task ID per prompt, run what it writes, check the "done when" condition, then commit.
