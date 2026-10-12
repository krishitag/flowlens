# Member 3: Dashboard, Demo & Report

You build what the reviewers actually see: the live dashboard, the paper, the slides and the backup demo video. **Never wait on anyone:** fill the database with fake events from hour 1 and build against that.

Source of truth: [docs/PLAN.md](../PLAN.md). If this file and the plan disagree, follow the plan.

---

## What you own

| You edit | You never edit |
|---|---|
| `dashboard/`, `paper/`, `README.md` | `ml/`, `models/`, `pipeline/`, `scenarios/`, `tests/`, `reports/`, and the shared files (`contracts/`, `requirements.txt`, `CLAUDE.md`, `docs/`) unless all 3 of you agree |

Branch prefix: `dashboard/` (for example `dashboard/alert-table`). Commit messages start with `[dash]`.

## Where your data comes from

- **Live data:** `data/events.db`, written by Member 2's pipeline (and by your fake generator until then).
- **Results:** `reports/results.json`, `reports/holdout.json`, `reports/explain_benchmark.json` and `reports/figures/*.png` from Member 1, plus `reports/pipeline_latency.json` from Member 2.
- **Paper text:** methodology sections from Member 1 (M1.9) and Member 2 (M2.10).

## The database you read (contract 4.3, `contracts/schema.sql`)

`data/events.db`, SQLite in WAL mode (so you can read while the pipeline writes).

**`traffic_windows`**: one row per 1-second window

| column | meaning |
|---|---|
| `ts` | simulated seconds since the run started |
| `flows`, `packets`, `bytes` | traffic in that window |
| `z_score` | Tier-1 anomaly score |
| `state` | `'NORMAL'` or `'ELEVATED'` |
| `scored`, `explained` | flows scored / explained in that window |

**`alerts`**: one row per flagged flow

| column | meaning |
|---|---|
| `id`, `ts`, `flow_idx`, `dst_port` | identity and time |
| `true_label` | ground truth, shown for demo honesty |
| `pred_label`, `pred_prob` | LightGBM's prediction and confidence |
| `if_score` | IsolationForest score |
| `source` | `'lgbm'`, `'iforest'` or `'both'` |
| `top_features` | JSON string: `[{"name","value","contribution","percentile"}]` |
| `explanation` | human-readable sentence(s) |
| `detect_ms`, `explain_ms` | per-flow latency |

**`run_meta`**: `key, value` (run summary)

Classes: `BENIGN`, `DoS`, `DDoS`, `PortScan`, `BruteForce`, `WebAttack`, `Bot`.

## Current status: you can use a real events.db now

Member 2's pipeline is finished, so you don't have to wait for it, and you may not need `fake_events.py` at all. To get a real `data/events.db` in the exact schema:
```
pip install -r requirements.txt        # macOS: also brew install libomp
python tests/make_fake_models.py       # fake models + test data (until Member 1's real ones arrive; don't commit them)
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```
Run your dashboard at the same time. `--speed 1` takes about 105 s and writes one window per second, so it's a true live test. Every run deletes and recreates the DB, so the dashboard must handle the file disappearing briefly.

**What the values look like in practice:**
- **`explanation`:** usually up to 3 sentences separated by **newlines** (`\n`), one per feature, e.g. `Flow Packets/s = 4,812 (above 99.9% of normal flows)`. If no feature stands out, it's a single fallback sentence instead.
- **`top_features[].contribution`:** positive means it pushed the flow toward "anomalous", for both models, so you can plot them on the same bar chart. `top_features` can hold fewer than 3 entries.
- **`if_score`:** NULL for alerts from NORMAL windows (IsolationForest only runs when ELEVATED). Lower means more anomalous.
- **`pred_label`:** always LightGBM's prediction. For `source = 'iforest'` it's often `BENIGN`, which means "anomalous, but not a known attack".
- **"Low confidence" tag:** show it when `if_score` is not NULL and `source` is `'lgbm'` or `'iforest'`. Both models ran, but only one flagged the flow.
- **`run_meta` keys** (written at the end of a run): `scenario`, `speed`, `total_flows`, `total_alerts`, `detect_ms_p50`, `detect_ms_p95`, `explain_ms_p50`, `explain_ms_p95`.
- **State timeline in `demo.json`:** ELEVATED from ts≈32–54 (DoS) and ts≈72–89 (PortScan).
- **Paper text from Member 2:** already in `paper/pipeline_section.md`. Its result numbers are `[placeholders]` until the real models are in.

---

## Tasks

### M3.1: `dashboard/fake_events.py`
- Write fake windows and alerts into `data/events.db` using the **exact** schema (create it from `contracts/schema.sql`).
- Make it look realistic: a BENIGN stretch, a spike that switches to ELEVATED, alerts with 3 `top_features` each, and a mix of `source` values.
- **Done when:** the dashboard has data from hour 1.

### M3.2: `dashboard/app.py` layout
- **Top row:** a state badge (green NORMAL / red ELEVATED), flows/s, packets/s, and alerts in the last 60s.
- **Main chart:** flows/s over time with ELEVATED periods shaded, and z-score on a secondary axis (Plotly).
- **Alert table:** the last 50 alerts, with time, dst port, predicted type, confidence, source and ground truth.
- Live refresh with `st.fragment(run_every=1)`.
- **Done when:** it refreshes every second. Run it with `streamlit run dashboard/app.py`.

### M3.3: Explanation panel
- Select an alert to show a horizontal bar chart of its top features' SHAP contributions, plus the explanation sentences.
- Show a **"low confidence"** tag when LightGBM and IsolationForest disagree.
- **Done when:** it reads and displays `top_features` JSON correctly.

### M3.4: Stats sidebar
- p50/p95 of detect and explain latency, computed from the `alerts` table.
- % of flows scored and explained in each state, computed from `traffic_windows`.
- **Done when:** the numbers update live.

### M3.5: Results tab
- A second tab that loads `reports/*.json` and figures and shows the F1 table, the holdout table, and the TreeSHAP vs Kernel SHAP chart.
- **Done when:** it works once Member 1 pushes the reports. Until then, show a "not available yet" message instead of crashing.

### M3.6: Paper (in `paper/`)
Assemble:
1. Revised abstract + problem (from PLAN.md Section 1).
2. The literature review from Review 1, **with the SHAP claim fixed**: TreeSHAP is fast, Kernel SHAP is the slow one.
3. Methodology sections from Member 1 and Member 2.
4. Results (the numbers from `reports/*.json`).
5. Limitations: low-and-slow attacks may never trigger ELEVATED (PLAN.md Section 1).
6. Conclusion.
- **Done when:** the draft is complete.

### M3.7: Review 2 slides
- Order: problem → what changed since Review 1 (the table in PLAN.md Section 1) → architecture → live demo → results → limitations.
- **Done when:** they're ready to present.

### M3.8: `README.md`
- Exact commands for setup, data download (with the Drive link for `data/processed/`), training, running the pipeline and running the dashboard.
- **Done when:** someone fresh can run the project from it.

### M3.9: Backup demo video
- Record the full `demo.json` scenario running with the dashboard, in case the live demo breaks on presentation day.
- **Done when:** it's saved and shared with the team.

---

## Timeline

| When | You |
|---|---|
| Hour 0–1 | Agree on the contracts with the team |
| Hour 1–3 | M3.1, M3.2 |
| **Checkpoint A (~Hour 3)** | Dashboard shows fake data |
| Hour 3–7 | M3.3, M3.4 |
| **Checkpoint B (end of Day 1)** | Full end-to-end run with the real pipeline |
| Day 2 morning | M3.5, start M3.6 |
| **Checkpoint C (midday)** | Results tab shows real numbers |
| Day 2 afternoon | M3.6–M3.8 |
| Day 2 evening | Rehearse the demo twice, M3.9 video, final paper read-through |

If you're behind, cut the Results tab and put the figures in the slides instead.

## Watch out for
- Only **read** the database in the dashboard. Writing is the pipeline's job (and `fake_events.py`'s, for testing).
- Use the exact column names from the schema. If you need a column that isn't there, raise it with the team. Don't add it yourself.
- Handle an empty or missing DB gracefully, since the dashboard may start before the pipeline does.
- Never commit `data/events.db`.

## Starter prompt for Claude Code
> I'm Member 3. Read docs/PLAN.md and CLAUDE.md. Implement task M3.1 in dashboard/fake_events.py following the schema in contracts/schema.sql (PLAN.md 4.3). Don't modify files outside dashboard/.

Do one task ID per prompt, run what it writes, check the "done when" condition, then commit.
