# FlowLens: Review 3 Guide

Prep notes for Review 3: what to say, which files to open, what to run, and how to do the live demo.

---

## 1. What the project is (the 30-second pitch)

**FlowLens is an explainable, real-time network intrusion detector.**

It takes real labelled network flows from the **CIC-IDS2017** dataset and replays them as live traffic, one 1-second window at a time. A machine-learning model (LightGBM plus an Isolation Forest) decides whether each flow is an attack. For every alert, the system also says **why**, in plain language, while traffic is still arriving:

> `Flow Packets/s = 4,812 (above 99.9% of normal flows)`

A Streamlit dashboard shows traffic, the system's state (NORMAL or ELEVATED), alerts and their explanations as they happen.

**The problem it solves:** monitoring tools usually separate traffic dashboards from security alerts, and an ML alert normally arrives as a bare label with no reason. Research on explainable intrusion detection uses SHAP to give reasons, but only **offline**, and mostly with **Kernel SHAP**, which takes about 2 seconds per flow. That's far too slow for live traffic.

**Our claim:** per-flow explanations *are* cheap enough for real time if you
1. use **tree models** and explain them with **TreeSHAP** (exact and fast) instead of Kernel SHAP, and
2. do the heavy work only when traffic looks abnormal, using a **two-tier design**.

We back this claim with measurements, not assertions.

---

## 2. Novelty: what's new

| Point | What to say |
|---|---|
| **Real-time explanations** | Most XAI-IDS papers explain offline. We explain every alert live. TreeSHAP takes **2.4 ms** per flow, against **~2–2.6 s** for Kernel SHAP: **~800–1,100× faster** (measured on our models, `reports/explain_benchmark.json`). |
| **Two-tier compute saving** | Tier 1 is a cheap EWMA monitor on flow rate. In NORMAL state only 10% of flows are scored. Only when traffic is abnormal (ELEVATED) do we score every flow with both models. Under stress: NORMAL scores 10% and explains 2.6% of flows; ELEVATED scores 100% and explains 18%. |
| **Known and unknown attacks** | LightGBM (supervised) names the attack type. The Isolation Forest (unsupervised, trained only on benign traffic) catches anomalies the classifier never saw. Each alert records which model flagged it (`lgbm`, `iforest`, `both`), and disagreement is shown as **low confidence ⚠**. |
| **Human-readable reasons** | SHAP values alone mean little to an analyst. We compare each top feature with the **benign percentile distribution** and turn it into a sentence ("above 99.9% of normal flows"). |
| **Explanation budget** | At most 300 explanations per window, most confident first, so even a flood stays inside the 1-second budget (p95 223 ms per window vs 1,251 ms without the cap). |
| **Honest evaluation** | A leave-one-attack-out test shows what happens with attacks the model never saw, and we report the cases where it fails (Bot, slow scan). |

---

## 3. How it works (architecture)

```
scenario.json ─▶ Replayer ─▶ Tier 1: EWMA monitor ─▶ Tier 2: detector ─▶ Explainer ─▶ SQLite (WAL) ─▶ Dashboard
                 1-s windows   NORMAL / ELEVATED      LightGBM (+ IForest)   TreeSHAP      events.db        Streamlit
```

**Offline half (`ml/`, run once):** raw CSVs → clean, dedupe, group labels, 70/15/15 split → train LightGBM, Isolation Forest, Random Forest baseline → evaluation reports.

**Online half (`pipeline/`, every 1-second window):**
1. **Replay:** sample flows from `test.parquet` according to the scenario (benign stretch, DoS burst, port scan, …).
2. **Tier 1:** EWMA z-score on flows per window. **ELEVATED** after 3 windows with z > 3; back to **NORMAL** after 5 windows with z < 2. The baseline freezes while ELEVATED, so an attack never becomes the new normal.
3. **Tier 2:** NORMAL → LightGBM on a random 10%. ELEVATED → LightGBM **and** Isolation Forest on every flow. Flag if LightGBM says attack with p ≥ 0.5, or the IForest score is below its threshold (set for ~1% false positives on benign traffic).
4. **Explain:** TreeSHAP on flagged flows (cap 300/window), top 3 features → sentences using benign percentiles.
5. **Store:** one `traffic_windows` row plus a batch of `alerts` rows in SQLite (WAL mode, so the dashboard reads while the pipeline writes).

**Classes:** BENIGN, DoS, DDoS, PortScan, BruteForce, WebAttack, Bot.
**Features:** 20 flow features, chosen by LightGBM importance. Destination port, IP addresses, flow IDs and timestamps are **never** features, because they would leak the answer.

---

## 4. Tech stack

| Purpose | Tool |
|---|---|
| Language | Python 3.11 |
| Data | pandas, numpy, pyarrow (parquet) |
| Models | LightGBM (classifier), scikit-learn (Isolation Forest, Random Forest baseline, metrics) |
| Explanations | `shap.TreeExplainer` (live); `KernelExplainer` only in the benchmark |
| Storage | joblib (models), SQLite in WAL mode (live events) |
| Dashboard | Streamlit (auto-refresh every 1 s) + Plotly |
| Testing | pytest (23 unit tests) |
| Dataset | CIC-IDS2017 (Canadian Institute for Cybersecurity, UNB) |
| Collaboration | GitHub, protected `main`, PRs with 1 review |

---

## 5. Project structure: files worth opening

If she asks to see code, open these, in this order:

| File | What to point at |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The problem, the claim, what changed since Review 1, contracts between team members |
| [ml/prepare.py](ml/prepare.py) | Cleaning, deduplication, label grouping, dropping port/IP features (leakage), stratified split |
| [ml/train.py](ml/train.py) | LightGBM, Isolation Forest (benign only, 1% FPR threshold), RF baseline, top-20 feature selection, benign percentile baselines |
| [pipeline/run.py](pipeline/run.py) | The main loop: one window → monitor → detect → explain → store |
| [pipeline/monitor.py](pipeline/monitor.py) | Tier 1: the EWMA z-score state machine (small and easy to explain) |
| [pipeline/detector.py](pipeline/detector.py) | Tier 2: 10% sampling vs full scoring, the flag rule, `lgbm`/`iforest`/`both` |
| [pipeline/explainer.py](pipeline/explainer.py) | TreeSHAP built once at startup, top 3 features, percentile sentences, the 300-per-window cap |
| [contracts/schema.sql](contracts/schema.sql) | The database the pipeline writes and the dashboard reads |
| [dashboard/app.py](dashboard/app.py) | Live view |
| [ml/benchmark_explain.py](ml/benchmark_explain.py) | The headline experiment: TreeSHAP vs Kernel SHAP |
| [reports/](reports/) | All the numbers: `results.json`, `holdout.json`, `explain_benchmark.json`, `pipeline_latency.json`, figures |
| [paper/paper.md](paper/paper.md) | Full write-up |

Full layout:

```
contracts/   SQLite schema shared by pipeline and dashboard
dashboard/   Streamlit app (live view, Results tab, theme)
docs/        PLAN.md (design), STATUS.md (progress)
ml/          data prep, training, evaluation, holdout test, SHAP benchmark
models/      trained models, feature list, labels, IForest threshold, benign baselines
paper/       paper sections, build script, demo script, slides
pipeline/    replayer, monitor, detector, explainer, store, run, latency report
reports/     results JSON + figures
scenarios/   demo, stress and slowscan traffic scripts
tests/       unit tests
```

---

## 6. Results (all from real CIC-IDS2017 data)

| What | Result |
|---|---|
| Explanation time per flow | **TreeSHAP 2.4 ms vs Kernel SHAP ~2–2.6 s → ~800–1,100× faster** |
| Classification, test set | Macro F1 **0.972** (LightGBM), 0.986 (Random Forest baseline) |
| False positives on benign | LightGBM flags **0.37%** of benign flows |
| Per class | DoS, DDoS, PortScan, BruteForce ≥ 0.998 F1. Weak: **WebAttack 0.86**, Bot 0.95 (smallest classes) |
| Unseen attack: DoS held out of training | **37.8%** still caught (IForest 33%, LightGBM 5%) |
| Unseen attack: Bot held out | 0% caught |
| Pipeline under stress (~1,100 flows/s) | **223 ms per 1-second window** at p95, well inside 1,000 ms |
| Live demo run | 6,550 alerts, **99.7% explained** |

**Why choose LightGBM over RF if RF scores higher?** Single-flow prediction is ~0.34 ms for LightGBM vs ~14 ms for RF, and TreeSHAP is fast on LightGBM's shallower boosted trees. For a live system, latency matters as much as 1.4 F1 points.

---

## 7. Advantages

- **Explains every alert in real time**, in plain language, not just a label.
- **Measured, not claimed:** latency and accuracy numbers come from scripts anyone can rerun.
- **Saves compute:** in normal traffic only 10% of flows are scored, and only flagged ones are explained.
- **Covers known and unknown attacks** with a supervised and an unsupervised model together.
- **Shows confidence:** analysts see which model flagged an alert and when the two disagree.
- **Bounded latency:** the per-window explanation cap keeps every window inside its 1-second budget.
- **No leakage:** port, IP, flow ID and timestamps excluded; duplicate rows removed before splitting.
- **Reproducible:** clone, install, run. Models and the test split come with the repo; fixed random seeds.

## 8. Limitations (say these before she asks)

- **Low-and-slow attacks:** a slow port scan never raises the flow rate enough to trigger ELEVATED, so it's only caught by the 10% sample (~10% of scan flows). This is the trade-off of tiering. `scenarios/slowscan.json` shows it.
- **Attacks that look normal:** at its 1% FPR threshold the Isolation Forest catches a third of unseen DoS but almost no Bot traffic.
- **WebAttack is the weakest class** (F1 0.86): only 321 test flows, and they look like normal web traffic.
- **Replayed, not captured, traffic:** flows come from CSV records, so latency excludes packet capture and feature extraction (CICFlowMeter would add that in a real deployment).
- **Unexplained alerts under very heavy load:** above 300 flagged flows in one window, the least confident ones are stored without an explanation.
- **One dataset:** CIC-IDS2017 is from 2017 and one lab network; results may not transfer to other networks without retraining.

**Future work:** live capture with CICFlowMeter, a per-destination monitor to catch slow scans, testing on newer datasets (CIC-IDS2018, UNSW-NB15), analyst feedback loop.

---

## 9. Before the review (10 minutes ahead)

From the repo root, in a terminal:

```bash
cd ~/Desktop/flowlens
git checkout main && git pull
source .venv/bin/activate
pytest tests/ -q                                                # expect: 23 passed
python -m pipeline.run --scenario scenarios/demo.json --speed 0  # dry run, ~10 s, ends with 6,550 alerts
```

Then:
1. Open **two terminals**, both in the repo root with `.venv` active.
2. **Terminal 1:** `streamlit run dashboard/app.py` → open http://localhost:8501, full screen, zoom 110–125%.
3. Check the **Results** tab shows numbers (if not, click **Reload reports**).
4. Have the **backup video** open in another window in case anything breaks.
5. Turn off notifications.

---

## 10. Live demo: run of show (~3–4 minutes)

**Terminal 2, at T = 0:**

```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```

The scenario is: benign 30 s → DoS 20 s → benign 20 s → PortScan 15 s → benign 20 s (~105 s total).

| Time | On screen | What to say |
|---|---|---|
| 0–30 s | Green **NORMAL**, ~40 flows/s, coverage ~10% | "This is normal traffic. Tier 1 just watches the flow rate. Tier 2 scores only a 10% sample, so we don't pay to score and explain everything." |
| ~30 s | Flow rate jumps to ~400/s, z-score crosses the red line | "A DoS attack starts. The z-score goes above 3…" |
| ~32 s | Red **ELEVATED**, shaded band, coverage 100% | "…three windows in a row, so we switch to ELEVATED. Now every flow is scored by LightGBM and the Isolation Forest." |
| 32–50 s | Alerts table fills, DoS in Alerts-by-type | **Toggle Pause live updates** in the sidebar. Go to *Why was it flagged?*, type a DoS alert ID, walk through the SHAP bars and the sentences: "This is the reason, in plain language, computed in under a millisecond." Point at the **true label** column: "we show ground truth so you can see it's correct." **Untoggle Pause.** |
| ~50–55 s | Back to **NORMAL** after 5 calm windows | "Attack over. Five calm windows and we drop back to sampling." |
| 70–85 s | PortScan, ELEVATED again | "A port scan: a different attack, and different features explain it." Show a PortScan alert, ideally one tagged **low confidence ⚠** (the two models disagreed). |
| ~105 s | **RUN COMPLETE** | Point at the sidebar: detect/explain latency per flow, and % scored/explained per state. "That's the saving from tiering." |
| After | **Results** tab | TreeSHAP vs Kernel SHAP speed-up first (the headline), then per-class F1, leave-one-attack-out, pipeline latency. |
| If asked | **How it works** tab | The pipeline and the slow-scan limitation. |

**If something breaks:** switch to the backup video. Don't debug in front of her.

---

## 11. Extra things you can run to prove it works

All of these run straight from the repo with what's on your laptop. Run them in Terminal 2 **after** the live demo (each pipeline run resets `data/events.db`).

| To show | Command | What to expect |
|---|---|---|
| **Unit tests pass** | `pytest tests/ -q` | `23 passed` in ~5 s |
| **Model accuracy** | `python ml/evaluate.py` | Per-class F1 for LightGBM and RF, macro F1 0.972 / 0.986, benign FPR. Writes `reports/results.json` + figures |
| **Latency under load** | `python -m pipeline.latency_report --scenario scenarios/stress.json` | ~100 windows at ~1,100 flows/s; e2e p95 ≈ 220 ms per window; % scored/explained by state |
| **The known limitation** | `python -m pipeline.run --scenario scenarios/slowscan.json --speed 0` | Stays **NORMAL** the whole time; only ~15–17 alerts from the slow scan. Honest weakness of tiering |
| **The explanation cap matters** | `python -m pipeline.run --scenario scenarios/stress.json --speed 0 --explain-cap 0` vs default | With cap 0 nothing is explained; default 300 keeps the window budget |
| **Headline benchmark** (slow) | `python ml/benchmark_explain.py` | TreeSHAP vs Kernel SHAP. Takes **~6 minutes**: show the existing `reports/explain_benchmark.json` and `reports/figures/shap_latency.png` instead, and only run it if she insists |
| **Unseen attacks** (slow) | `python ml/holdout.py` | Retrains without DoS / Bot and reports recall. Show `reports/holdout.json` instead unless asked |

The three report scripts (`evaluate.py`, `latency_report`, `benchmark_explain.py`) overwrite files in `reports/` with slightly different timings each run. Afterwards run `git checkout -- reports/` so you don't commit timing noise by accident.

**Don't run** `python ml/train.py` or `tests/make_fake_models.py` during the review: both overwrite the models in `models/`.

### What the 23 unit tests check

| File | Checks |
|---|---|
| `tests/test_monitor.py` (7) | Steady traffic stays NORMAL; a sustained spike flips to ELEVATED after 3 windows; a single spike doesn't; return to NORMAL only after 5 calm windows; the calm streak resets on a spike; nothing flips during warm-up; the baseline isn't learned while ELEVATED |
| `tests/test_explainer.py` (9) | Percentile lookup against the benign baselines; "above 99.9%", "below all", "above X%", "below X%" wording; tied zeros and binary flags handled; sentence format |
| `tests/test_explain_cap.py` (5) | Under the cap everything is explained; over it the most confident LightGBM alerts go first, then IForest-only by lowest score; cap 0 and empty windows work |

---

## 12. Questions she might ask

| Question | Answer |
|---|---|
| Why not deep learning? | Tree models are accurate on tabular flow features, fast, and TreeSHAP gives *exact* SHAP values in milliseconds. Deep models would need slow approximate explainers. |
| Why both LightGBM and Isolation Forest? | Different jobs: LightGBM names known attacks; IForest is trained only on benign traffic, so it can flag things LightGBM never saw. The holdout test shows this: unseen DoS caught 5% by LightGBM, 33% by IForest. |
| Is 97% F1 too good, is there leakage? | We excluded destination port, IPs, flow ID and timestamps, and removed duplicate rows before splitting. 0.97 macro F1 is in line with published CIC-IDS2017 results; WebAttack at 0.86 shows it isn't trivially perfect. |
| Why is it "real time" if it's a replay? | The pipeline processes each 1-second window as it would live traffic and must finish inside 1 s. We replay real flows so we have ground truth labels. Packet capture is the missing piece and is listed as a limitation. |
| What is SHAP? | A game-theory method that gives each feature a share of the model's decision. TreeSHAP computes it exactly for tree models in polynomial time; Kernel SHAP approximates it for any model by sampling, which is why it's ~1,000× slower. |
| What does EWMA do? | Exponentially weighted moving average of flows/s (alpha 0.1) and its variance. The z-score says how unusual the current window is compared with recent normal traffic. |
| Why 3 windows to enter and 5 to leave? | Hysteresis: one noisy window shouldn't trigger ELEVATED, and we don't want to flap in and out during an attack. |
| What changed since Review 2? | *(Fill in with any feedback you acted on after Review 2.)* What's complete now: real models on CIC-IDS2017, the explanation cap (p95 per window under stress 1,251 ms → 223 ms), the full paper with real numbers, and a README that lets anyone clone and run it. |
| Why does the pipeline explain in ~0.5 ms but the benchmark says 2.4 ms? | The benchmark times one flow at a time; the pipeline explains a whole window's flagged flows in one batch, so the cost per flow is lower. |
