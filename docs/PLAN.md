# Explainable Real-Time Network Anomaly Detection — 2-Day Build Plan

> Commit this file at `docs/PLAN.md`. Every member (and every member's Claude Code) works from it.
> Contracts in Section 4 are frozen once agreed. Changing them needs a PR approved by all 3.

---

## 1. The problem (revised from Review 1)

Network monitoring tools usually split **visibility** (traffic dashboards) from **security** (alerts). When an ML detector raises an alert, the analyst gets a label but no reason. The XAI papers we reviewed explain detections with SHAP, but only offline, and mostly with **Kernel SHAP**, which is far too slow to run per connection on live traffic.

**Our claim:** per-flow explanations *are* cheap enough for real-time monitoring if you:
1. use **tree-based models** and explain them with **TreeSHAP** (exact, fast) instead of Kernel SHAP, and
2. only run heavy work (full scoring + explanation) when traffic is abnormal, using a **two-tier design**.

We prove this with measurements, not assertions: detection and explanation latency per flow, TreeSHAP vs Kernel SHAP, accuracy per attack class, and a test on an attack type the classifier never saw during training.

### What changed from Review 1 (say this explicitly in Review 2)
| Review 1 | Now | Why |
|---|---|---|
| "SHAP is too slow, so we avoid it" | TreeSHAP on tree models, benchmarked against Kernel SHAP | TreeSHAP is fast; the slow one is Kernel SHAP. A reviewer would catch the original claim. |
| Custom Python traffic simulator | Replay real labeled flows from CIC-IDS2017 as a live stream | Real traffic features, real labels, less code, no fake easy attacks |
| "Predictive" framework | Removed | Nothing in the system predicts future traffic |
| "Random Forest **or** Isolation Forest" | LightGBM (supervised, attack type) **and** Isolation Forest (unsupervised, unseen attacks); RF as baseline | They do different jobs; together they cover known + unknown attacks |
| "Tested on realistic datasets" (unnamed) | CIC-IDS2017 + leave-one-attack-out test | Named, reproducible, and the holdout shows how it behaves on attacks it wasn't trained on |
| Analyst usability metric | Removed | Can't be measured in 2 days |

### Success metrics (report these numbers)
- Macro F1 and per-class F1 (LightGBM, RF baseline)
- False positive rate on benign traffic
- Leave-one-attack-out recall: LightGBM alone vs Isolation Forest alone vs either
- Detection latency per flow, p50/p95 (ms)
- Explanation latency per flow, p50/p95: **TreeSHAP vs Kernel SHAP**
- Compute saved by tiering: % of flows fully scored/explained in NORMAL vs ELEVATED state

### Known limitation (put it in the report, don't hide it)
Low-and-slow attacks (e.g. a slow port scan) may never push aggregate traffic high enough to trigger ELEVATED, so in NORMAL state they are only caught by sampling. That's the trade-off of tiering.

---

## 2. System overview

```
 scenario.json
      │
      ▼
┌─────────────┐  flows   ┌──────────────┐  state  ┌──────────────────────┐  flagged  ┌─────────────┐
│  Replayer   │ ───────▶ │ Tier 1       │ ──────▶ │ Tier 2 Detector      │ ────────▶ │ Explainer   │
│ (test flows │          │ EWMA monitor │         │ LightGBM + IForest   │           │ TreeSHAP +  │
│  in time)   │          │ NORMAL/ELEV. │         │ (sampled in NORMAL,  │           │ text        │
└─────────────┘          └──────┬───────┘         │  all in ELEVATED)    │           └──────┬──────┘
                                │                  └──────────────────────┘                  │
                                ▼                                                            ▼
                         ┌──────────────────────────── SQLite (WAL) ─────────────────────────────┐
                         │   traffic_windows                     alerts                          │
                         └──────────────────────────────────┬────────────────────────────────────┘
                                                            ▼
                                                   Streamlit dashboard
```

- **Tier 1:** every 1-second window, compute flows/s and packets/s. EWMA mean and variance (alpha = 0.1). If z-score > 3 for 3 consecutive windows → ELEVATED. Back to NORMAL after 5 consecutive windows with z < 2. (Changed from "10 windows with z < 1", which often never recovered under realistic Poisson traffic; simulation in `paper/pipeline_section.md`.) The baseline is frozen while ELEVATED.
- **Tier 2:** NORMAL → score a random 10% of flows with LightGBM. ELEVATED → score every flow with LightGBM **and** Isolation Forest.
- **Flag rule:** flagged if LightGBM predicts non-BENIGN with prob ≥ 0.5, **or** Isolation Forest score is past its threshold. Record which (`lgbm`, `iforest`, `both`). `both` disagreeing with each other = show "low confidence" on the dashboard.
- **Explainer:** TreeSHAP on flagged flows only. Use LightGBM contributions for the predicted class; if only IForest flagged it, use TreeSHAP on IForest. Take top 3 features pushing toward "anomalous", and turn each into a sentence using benign percentiles, e.g. `Flow Packets/s = 4,812 (above 99.9% of normal flows)`.

---

## 3. Tools

| Purpose | Tool |
|---|---|
| Language | Python 3.11 (shap is happiest here) |
| Data | pandas, numpy, pyarrow (parquet) |
| Models | lightgbm, scikit-learn (IsolationForest, RandomForest, metrics) |
| Explanations | shap (TreeExplainer; KernelExplainer only for the benchmark) |
| Persistence | joblib for models, SQLite in WAL mode for events |
| Dashboard | Streamlit (`st.fragment(run_every=1)` for live refresh) + Plotly |
| Repo | GitHub, one folder per member, PRs into `main` |
| Coding | Claude Code, with `CLAUDE.md` at repo root pointing to this plan |

`requirements.txt`:
```
pandas
numpy
pyarrow
scikit-learn
lightgbm
shap
joblib
streamlit
plotly
pytest
```

**Dataset:** CIC-IDS2017, the **MachineLearningCSV / MachineLearningCVE** CSVs (one CSV per capture day, ~78 flow features + `Label`). Get it from the UNB CIC site (form before download) or a Kaggle mirror. **Member 1 starts this download in the first 10 minutes.** Raw data is never committed.

---

## 4. Contracts (freeze in Hour 1)

### 4.1 Files Member 1 produces (committed to `models/` and `data/processed/` is gitignored but shared via Drive)
| Path | Content |
|---|---|
| `models/lgbm.joblib` | trained LightGBM multiclass model |
| `models/iforest.joblib` | IsolationForest trained on BENIGN train flows only |
| `models/rf.joblib` | RandomForest baseline (not used in pipeline; skip committing if > 50 MB) |
| `models/features.json` | ordered list of feature names the models expect |
| `models/labels.json` | `{"0": "BENIGN", "1": "DoS", ...}` |
| `models/iforest_threshold.json` | `{"threshold": <float>}` (score below this = anomalous), set for ~1% FPR on benign validation |
| `models/baselines.json` | `{feature: [q0, q1, ..., q100, q99_9]}` — 101 percentiles of BENIGN train + 99.9th as last element |
| `data/processed/test.parquet` | test split: all `features.json` columns + `label` (grouped class) + `dst_port` |
| `data/processed/holdout_<class>.parquet` | flows of the held-out attack class (Section 5, Member 1) |

### 4.2 Label grouping
`BENIGN`, `DoS` (Hulk, GoldenEye, slowloris, Slowhttptest), `DDoS`, `PortScan`, `BruteForce` (FTP-Patator, SSH-Patator), `WebAttack` (all three Web Attack labels), `Bot`. **Drop** Infiltration and Heartbleed (too few rows).

### 4.3 SQLite schema (`contracts/schema.sql`), DB at `data/events.db`
```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS traffic_windows (
  ts        REAL PRIMARY KEY,   -- simulated seconds since run start
  flows     INTEGER,
  packets   INTEGER,
  bytes     INTEGER,
  z_score   REAL,
  state     TEXT,               -- 'NORMAL' | 'ELEVATED'
  scored    INTEGER,            -- flows scored by tier 2 in this window
  explained INTEGER             -- flows explained in this window
);

CREATE TABLE IF NOT EXISTS alerts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           REAL,
  flow_idx     INTEGER,         -- row index in test.parquet
  dst_port     INTEGER,
  true_label   TEXT,            -- ground truth, shown for demo honesty
  pred_label   TEXT,
  pred_prob    REAL,
  if_score     REAL,
  source       TEXT,            -- 'lgbm' | 'iforest' | 'both'
  top_features TEXT,            -- JSON: [{"name","value","contribution","percentile"}]
  explanation  TEXT,            -- human sentence(s)
  detect_ms    REAL,
  explain_ms   REAL
);

CREATE TABLE IF NOT EXISTS run_meta (key TEXT PRIMARY KEY, value TEXT);
```

### 4.4 Scenario file (`scenarios/*.json`)
```json
{
  "window_s": 1,
  "segments": [
    {"label": "BENIGN",   "rate": 40,  "duration": 30},
    {"label": "DoS",      "rate": 400, "duration": 20, "benign_mix": 0.3},
    {"label": "BENIGN",   "rate": 40,  "duration": 20},
    {"label": "PortScan", "rate": 200, "duration": 15, "benign_mix": 0.5},
    {"label": "BENIGN",   "rate": 40,  "duration": 20}
  ]
}
```
`rate` = flows per simulated second, sampled from `test.parquet` rows with that label.

---

## 5. Work distribution

### Repo layout and ownership
```
.
├── CLAUDE.md                 # shared — changes need all 3
├── README.md                 # Member 3 (final run instructions)
├── requirements.txt          # shared
├── contracts/schema.sql      # shared
├── docs/PLAN.md              # shared
├── ml/                       # Member 1 only
│   ├── prepare.py
│   ├── train.py
│   ├── evaluate.py
│   ├── holdout.py
│   └── benchmark_explain.py
├── models/                   # Member 1 only (artifacts)
├── pipeline/                 # Member 2 only
│   ├── replayer.py
│   ├── monitor.py
│   ├── detector.py
│   ├── explainer.py
│   ├── store.py
│   └── run.py
├── scenarios/                # Member 2
├── dashboard/                # Member 3 only
│   ├── app.py
│   └── fake_events.py
├── reports/                  # Member 1 writes results.json + figures; Member 2 writes pipeline_latency.json
│   └── figures/
├── paper/                    # Member 3 (each member writes own methodology section)
└── data/                     # gitignored
```

**Rule:** you only edit your own folders. Shared files change through a PR all 3 approve. This alone prevents 90% of merge pain.

---

### Member 1 — ML & evaluation

**Branch prefix:** `ml/`

| # | Task | Output | Done when |
|---|---|---|---|
| M1.1 | Download CIC-IDS2017 MachineLearningCSV | `data/raw/*.csv` | Files on disk |
| M1.2 | `ml/prepare.py`: load all CSVs, strip whitespace from column names, drop duplicate column (`Fwd Header Length` appears twice), replace ±inf with NaN and drop those rows, drop exact duplicate rows, group labels (4.2), keep `Destination Port` as `dst_port` **but not as a feature** (leakage). Sample: cap each attack class at 50k rows, BENIGN at 300k. Stratified 70/15/15 train/val/test split. | `data/processed/{train,val,test}.parquet` | Script runs end to end, prints class counts |
| M1.3 | **v0 quick model (push within ~3 hours of start):** LightGBM on all features, default params, `class_weight='balanced'`. IForest on BENIGN train. Write every file in 4.1. | `models/*` v0 | Member 2 can load and predict |
| M1.4 | Feature reduction: take top 20 features by LightGBM gain importance, retrain on those. Use the 20-feature version as final (faster, readable explanations). | updated `models/*`, `features.json` | Macro F1 within ~1–2 points of all-feature model |
| M1.5 | `ml/train.py` final: LightGBM (~200 trees), IForest (100 trees, threshold at ~1% benign-val FPR), RF baseline (100 trees, `n_jobs=-1`) | final `models/*` | Reproducible with one command |
| M1.6 | `ml/evaluate.py`: per-class precision/recall/F1, macro F1, benign FPR, confusion matrix for LightGBM and RF; per-flow inference latency | `reports/results.json`, `reports/figures/confusion_lgbm.png`, `per_class_f1.png` | Numbers in JSON |
| M1.7 | `ml/holdout.py`: retrain LightGBM **without** one attack class (do `Bot`, then `WebAttack` if time). On that class's flows report recall of LightGBM alone, IForest alone, either. | `reports/holdout.json`, `holdout_<class>.parquet` | Table ready for paper |
| M1.8 | `ml/benchmark_explain.py`: on 200 flagged test flows, time TreeSHAP per flow vs Kernel SHAP per flow (Kernel SHAP: background = 100 benign samples, only 50 flows — it's slow). Report mean, p50, p95. | `reports/explain_benchmark.json`, `figures/shap_latency.png` | The headline result exists |
| M1.9 | Write paper sections: Dataset & Preprocessing, Models, Evaluation results | text to Member 3 | Merged into `paper/` |

---

### Member 2 — Streaming pipeline & explanations (backend)

**Branch prefix:** `pipeline/`

| # | Task | Output | Done when |
|---|---|---|---|
| M2.1 | `pipeline/store.py`: create DB from `contracts/schema.sql`, helpers `insert_window()`, `insert_alerts(batch)`, `set_meta()`. Batch inserts per window. | DB file | Dashboard can read while pipeline writes (WAL) |
| M2.2 | `pipeline/replayer.py`: reads scenario JSON + `test.parquet`, yields `(ts, window_flows_df)` per window, sampling rows per segment label with `benign_mix`. `--speed` multiplier (1 = real time, 0 = as fast as possible). | generator | Prints per-window counts for demo scenario |
| M2.3 | `pipeline/monitor.py`: EWMA tier-1 logic from Section 2. Pure function/class, easy to unit test. | state per window | State flips to ELEVATED during DoS segment |
| M2.4 | `pipeline/detector.py`: loads `models/*`, NORMAL → 10% sample, ELEVATED → all flows; applies flag rule; times `detect_ms` per flow (batch time / batch size). **Before M1.3 lands, use a stub that flags randomly** so you're never blocked. | flagged rows | Works with v0 models |
| M2.5 | `pipeline/explainer.py`: `shap.TreeExplainer` built **once** at startup for LightGBM and IForest. For each flagged flow: contributions for predicted class, top 3 positive, percentile from `baselines.json` via `np.searchsorted`, sentence template. Times `explain_ms`. | `top_features` JSON + `explanation` | Sentences read sensibly |
| M2.6 | `pipeline/run.py`: wires everything. CLI: `python -m pipeline.run --scenario scenarios/demo.json --speed 1`. Writes windows + alerts every window. Writes run summary to `run_meta`. | runnable pipeline | End-to-end with dashboard |
| M2.7 | Scenarios: `demo.json` (for live demo, ~2 min), `stress.json` (high rate, speed 0, for latency numbers), `slowscan.json` (low-rate PortScan, to show the known limitation honestly) | `scenarios/*.json` | All run |
| M2.8 | Latency report: from a `stress.json` run, p50/p95 of detect_ms, explain_ms, end-to-end per window; % flows scored/explained in NORMAL vs ELEVATED | `reports/pipeline_latency.json` | Numbers for paper |
| M2.9 | Minimal tests: `tests/test_monitor.py` (state transitions), `tests/test_explainer.py` (percentile + sentence) | tests pass | `pytest` green |
| M2.10 | Write paper sections: System Architecture, Two-Tier Design, Explanation Generation, Latency results | text to Member 3 | Merged into `paper/` |

---

### Member 3 — Dashboard, demo, report

**Branch prefix:** `dashboard/`

| # | Task | Output | Done when |
|---|---|---|---|
| M3.1 | `dashboard/fake_events.py`: writes fake windows + alerts into `data/events.db` using the exact schema, so the dashboard is built **without waiting** for anyone. (Skipped: the real pipeline + `tests/make_fake_models.py` produced a real `events.db` first.) | fake DB | Dashboard has data from hour 1 |
| M3.2 | `dashboard/app.py` layout: **Top row:** state badge (green NORMAL / red ELEVATED), flows/s, packets/s, alerts in last 60s. **Main chart:** flows/s over time with ELEVATED periods shaded, z-score in a second panel underneath on the same time axis (originally a secondary y-axis; changed for readability). **Alert table:** last 50 alerts — time, dst port, predicted type, confidence, source, ground truth. | page | Refreshes every 1s via `st.fragment(run_every=1)` |
| M3.3 | Explanation panel: select an alert → horizontal bar chart of top features' SHAP contributions + the explanation sentences + "low confidence" tag if LightGBM and IForest disagree | panel | Reads `top_features` JSON |
| M3.4 | Stats sidebar: detect/explain latency p50/p95 from alerts table, % flows scored and explained per state | sidebar | Live numbers |
| M3.5 | Results tab: loads `reports/*.json` and figures → shows F1 table, holdout table, TreeSHAP vs Kernel SHAP chart | second tab | Works once Member 1 pushes reports |
| M3.6 | Paper: assemble `paper/` — revised abstract + problem (Section 1 of this plan), keep lit review from Review 1 (fix the SHAP claim), merge methodology sections from M1 and M2, results, limitations, conclusion | paper draft | Complete document |
| M3.7 | Review 2 slides: problem → what changed → architecture → live demo → results → limitations | slides | Ready to present |
| M3.8 | `README.md`: setup, data download, train, run pipeline, run dashboard (exact commands) | README | Someone fresh can run it |
| M3.9 | **Record a backup demo video** of the full scenario running (in case the live demo breaks on presentation day) | video | Saved and shared |

---

## 6. Timeline (2 days)

### Day 1
| When | All / Member 1 | Member 2 | Member 3 |
|---|---|---|---|
| Hour 0–1 | **All together:** create repo, push skeleton + `CLAUDE.md` + `contracts/` + this plan. Agree contracts. M1 starts dataset download. | | |
| Hour 1–3 | M1.2 prepare | M2.1–M2.3 (store, replayer on a tiny fake parquet, monitor) | M3.1–M3.2 |
| **Checkpoint A (~Hour 3)** | M1 pushes **v0 models + test.parquet** (share parquet via Drive) | Pipeline runs with stub detector | Dashboard shows fake data |
| Hour 3–7 | M1.4–M1.5 | M2.4–M2.6 against v0 models | M3.3–M3.4 |
| **Checkpoint B (end of Day 1)** | **Full end-to-end run:** replay → detect → explain → live dashboard, on v0 models. Merge everything to `main`. | | |

### Day 2
| When | Member 1 | Member 2 | Member 3 |
|---|---|---|---|
| Morning | M1.6–M1.8 (eval, holdout, SHAP benchmark) | M2.7–M2.9 (scenarios, latency, tests); swap in final models | M3.5; start paper M3.6 |
| **Checkpoint C (midday)** | All `reports/*.json` pushed | `pipeline_latency.json` pushed | Results tab shows real numbers |
| Afternoon | M1.9 paper sections | M2.10 paper sections | M3.6–M3.8 |
| **Code freeze (late afternoon)** | No new features after this. Only bug fixes via PR. | | |
| Evening | **All:** full demo rehearsal twice, M3.9 backup video, final paper read-through | | |

If you're behind at Checkpoint B, cut in this order: RF baseline → second holdout class → `slowscan.json` → results tab in dashboard (put figures in slides instead). **Never cut** the SHAP latency benchmark — it's the core claim.

---

## 7. GitHub workflow

- **Repo:** one repo, `main` is always runnable.
- **Branches:** `ml/<task>`, `pipeline/<task>`, `dashboard/<task>` — e.g. `ml/prepare-data`, `pipeline/explainer`.
- **Issues:** create one issue per task ID above (M1.1 … M3.9), assign to the owner, label `ml` / `pipeline` / `dashboard` / `paper`. Close via PR (`Closes #12`).
- **PRs:** small and often — at least one merge per member before each checkpoint. `main` is protected: every PR needs **1 approval** from another member before it can merge (no self-merging), and direct pushes and force-pushes to `main` are blocked. PRs touching shared files (`contracts/`, `requirements.txt`, `CLAUDE.md`, `docs/`) should be seen by both other members. Squash-merge, and keep `Co-authored-by: Claude` lines out of the final commit message.
- **.gitignore:** `data/`, `*.db`, `__pycache__/`, `.venv/`, large model files (> 50 MB).
- **Large files:** never commit raw CSVs or parquet. Share `data/processed/` via Google Drive link in README.
- **Commit messages:** `[ml] add label grouping`, `[pipeline] tier1 ewma monitor`, `[dash] alert table`.

---

## 8. Using Claude Code without wrecking each other's work

1. `CLAUDE.md` at repo root tells Claude Code the contracts and folder ownership. Don't delete it.
2. Start each session with your role, e.g.:
   > "I'm Member 2. Read docs/PLAN.md and CLAUDE.md. Implement task M2.5 in pipeline/explainer.py following contract 4.1 and the explainer description in Section 2. Don't modify files outside pipeline/ and tests/."
3. One task ID per session/prompt. Commit after each working task.
4. **Run what it writes.** Claude Code will happily produce code that looks right and isn't. Every task has a "done when" — check it yourself.
5. If Claude Code wants to change a contract (column name, schema, file path), stop and raise it with the team instead.
6. Watch for silent data leakage (IPs, ports, timestamps sneaking into features) and accuracy that looks too good (> 99.5% macro F1 usually means leakage or duplicates across splits).
