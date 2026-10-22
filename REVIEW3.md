# FlowLens: Review 3 Guide

**Course:** Computer Networks (VIT) · **Team:** Krishita Gupta, Krish Singh, Vedika

Read this top to bottom once before the review. Sections 1–3 explain the project from zero. Section 6 is the live demo script. Section 10 is the viva questions.

---

## 1. The project in one paragraph

FlowLens watches network traffic, spots attacks, and **tells you why** each one looks like an attack, while the traffic is still arriving. We take real recorded traffic from a public dataset (**CIC-IDS2017**) and replay it as if it were live. Every second, a cheap check decides whether traffic looks normal. If it doesn't, two machine-learning models check every connection, and for each one they flag, a method called **TreeSHAP** names the 3 measurements that pushed the model to flag it. It turns them into plain sentences like *"Flow Duration = 36 (below 92% of normal flows)"*. A live dashboard shows all of it.

**Why this is hard / why it matters:** normal ML security tools give you a label ("DoS!") with no reason. Research papers that *do* give reasons use a slow method called **Kernel SHAP**, which takes about **2 seconds per connection**, far too slow when hundreds of connections arrive every second. We show the reason can be computed in **2.4 ms**, about **800–1,100× faster**, so explanations can be live.

### The one line to memorise

> **"FlowLens makes network attack detection explainable in real time, and saves compute by only doing the heavy work when traffic looks abnormal."**

---

## 2. The basics, in simple words

### 2.1 What is a flow?

A **flow** is one network conversation between two computers: e.g. your laptop opening a connection to a web server, sending some packets, getting some back, and closing. The dataset doesn't store the raw packets; it stores **one row per flow** with ~78 numbers describing it (how long it lasted, how many bytes each way, gaps between packets, TCP flags…), plus a label saying whether it was normal or which attack it was.

### 2.2 What are features?

A **feature** is one measurable detail about a flow that the model looks at. Think of a doctor checking a patient: temperature, heart rate, blood pressure. Those are the doctor's features.

The dataset has 78 features. We kept the **20 most useful** (ranked by LightGBM's own importance score). Fewer features = faster model and explanations a human can read. The models lost almost no accuracy.

The features that matter most in our demo, in plain words:

| Feature (real name) | What it means |
|---|---|
| `Flow Duration` | How long the conversation lasted (microseconds) |
| `Flow IAT Max` | The longest gap between two packets (IAT = inter-arrival time) |
| `Total Length of Fwd Packets` | Total bytes the client sent |
| `Total Length of Bwd Packets` | Total bytes the server sent back |
| `Total Backward Packets` | Number of packets the server sent back |
| `Init_Win_bytes_backward` / `_forward` | The TCP window size in the first packet: how much data that side says it's ready to receive |
| `PSH Flag Count` | Packets with the TCP **PSH** ("deliver this now") flag set |
| `Idle Min` / `Idle Mean` | How long the connection sat doing nothing |
| `Fwd Header Length` | Total bytes of headers the client sent |
| `min_seg_size_forward` | Smallest TCP segment the client sent |

All 20 are in `models/features.json`.

**What we deliberately do NOT use:** destination port, IP addresses, flow ID, timestamps. In this dataset those give away the answer (e.g. every attack came from one attacker IP), so the model would "cheat" and fail on any other network. This is called **data leakage**.

### 2.3 What are the "top 3 features"?

For **each alert**, the 3 features that pushed the model **most** toward calling it an attack. They change from alert to alert, and from attack type to attack type.

Real examples from our demo run (`data/events.db`):

**A DoS alert** (true label DoS, model 99.99% sure):
```
Init_Win_bytes_backward = 235 (typical for normal flows, percentile 73)
Total Length of Bwd Packets = 11,595 (above 95% of normal flows)
Flow IAT Max = 83,400,000 (above 99% of normal flows)
```
*In words:* the connection had an 83-second gap between packets. Our DoS class includes **slowloris / slowhttptest**, which open connections and keep them hanging to tie up the server, so huge gaps are exactly the signature.

**A PortScan alert** (true label PortScan, 99.9% sure):
```
Flow Duration = 36 (below 92% of normal flows)
PSH Flag Count = 1 (same value as about 27% of normal flows)
Total Length of Fwd Packets = 2 (typical for normal flows, percentile 13)
```
*In words:* the connection lasted **36 microseconds** and sent 2 bytes. A port scanner knocks on a port and leaves immediately, so super-short tiny flows are the signature.

Across all 6,550 demo alerts, DoS is mostly explained by `Init_Win_bytes_backward`, `Total Length of Bwd Packets` and `Flow IAT Max`; PortScan by `Flow Duration` and `PSH Flag Count`. **Different attacks → different reasons**, which is what you'd expect if the explanations are real.

**"Why is a 'typical' value in the top 3?"** (good viva question) SHAP measures how much a feature *moved the model's decision*, not how unusual it is alone. A value can be ordinary by itself but matter in combination (e.g. window size 235 together with a huge gap). The percentile text just tells the analyst where the value sits compared with normal traffic.

### 2.4 What is SHAP?

**SHAP** (SHapley Additive exPlanations) comes from game theory. Imagine 20 players (features) winning a prize (the model's score). SHAP fairly splits the prize: how much did each player contribute? Big positive share = pushed hard toward "attack".

- **Kernel SHAP:** works for *any* model by trying lots of combinations and estimating. Slow: **~2–2.6 s per flow**.
- **TreeSHAP:** works only for *tree models*, but uses the tree structure to get the **exact** answer quickly: **2.4 ms per flow**.

That gap (~800–1,100×) is our headline result, and it's *why* we picked tree models.

### 2.5 The percentile sentence

Each top feature is compared with **normal (benign) traffic**. During training we stored, for each feature, the 0th, 1st, …, 100th percentile of benign flows, plus the 99.9th (`models/baselines.json`). If a value is bigger than 99.9% of benign values, the sentence says *"above 99.9% of normal flows"*. That turns a raw SHAP number into something a human understands.

### 2.6 The two ML models

| Model | Type | In simple words | Its job |
|---|---|---|---|
| **LightGBM** | Supervised (learns from labelled examples) | Hundreds of small decision trees, each one fixing the mistakes of the ones before ("gradient boosting") | Says **which** attack: DoS, DDoS, PortScan, BruteForce, WebAttack, Bot, or BENIGN |
| **Isolation Forest** | Unsupervised (trained on **normal traffic only**) | Randomly splits data; weird points get isolated in very few splits | Says **"this looks unusual"**, even for attacks LightGBM never saw |
| Random Forest | Supervised | Many independent decision trees that vote | **Baseline only**, to compare against. Not used live |

**Flag rule:** a flow becomes an alert if LightGBM says "attack" with ≥ 50% probability, **or** the Isolation Forest score is past its threshold (set so it falsely flags only ~1% of normal traffic). Each alert records who flagged it: `lgbm`, `iforest` or `both`.

**Low confidence ⚠:** both models looked at the flow but only one flagged it. The dashboard marks these so the analyst knows to double-check.

### 2.7 The two tiers

Think of airport security: everyone walks through a cheap metal detector (Tier 1); only if it beeps do you get the full bag search (Tier 2).

**Tier 1, the quick check (`pipeline/monitor.py`)**
- Every 1-second window, count the flows.
- Keep a running average of "normal" flow count using **EWMA** (exponentially weighted moving average: recent windows count more, old ones fade out; alpha = 0.1).
- Compute a **z-score**: how many standard deviations this window is above normal. z = 3 means "very unusual".
- **NORMAL → ELEVATED** after **3 windows in a row** with z > 3.
- **ELEVATED → NORMAL** after **5 calm windows in a row** with z < 2.
- While ELEVATED, the average stops learning, so a long attack never becomes "the new normal".
- Different enter/exit rules (3 vs 5, z 3 vs 2) are called **hysteresis**: it stops the state flickering on/off from one noisy window.

**Tier 2, the detailed check (`pipeline/detector.py`)**
- **NORMAL:** LightGBM checks a random **10%** of flows.
- **ELEVATED:** LightGBM **and** Isolation Forest check **100%** of flows.

**Then the explainer (`pipeline/explainer.py`)** runs TreeSHAP on flagged flows only, **max 300 per window**, most confident first. Without that cap, a flood of alerts made one window take 1,251 ms (over the 1-second budget); with it, 223 ms.

**Why two tiers?** Scoring and explaining every flow all the time wastes compute. Under our stress test: in NORMAL we scored 10% and explained 2.6% of flows; in ELEVATED, 100% scored and 18% explained.

### 2.8 Attack classes (what each one is)

| Class | What the attacker does |
|---|---|
| **DoS** | Overloads one server from one machine (Hulk, GoldenEye, slowloris, slowhttptest) |
| **DDoS** | Same, from many machines at once |
| **PortScan** | Knocks on many ports to find which services are open (reconnaissance) |
| **BruteForce** | Guesses passwords over and over (FTP-Patator, SSH-Patator) |
| **WebAttack** | Attacks a website: brute-force login, XSS, SQL injection |
| **Bot** | An infected machine talking to its controller |
| **BENIGN** | Normal traffic |

We dropped Infiltration and Heartbleed: too few examples to learn from.

### 2.9 Metric words you'll hear

| Word | Meaning |
|---|---|
| **Precision** | Of everything we flagged as X, how much really was X |
| **Recall** | Of all real X, how much we caught |
| **F1** | One number combining precision and recall (1.0 = perfect) |
| **Macro F1** | Average F1 over all 7 classes, each class counted equally (so small classes matter) |
| **False positive rate (FPR)** | % of normal traffic wrongly flagged |
| **p50 / p95** | Median / 95th percentile time: "95% of windows were faster than this" |
| **Latency** | How long something takes |

---

## 3. The flow (the pipeline)

```
scenario.json ─▶ Replayer ─▶ Tier 1: EWMA monitor ─▶ Tier 2: detector ─▶ Explainer ─▶ SQLite (WAL) ─▶ Dashboard
                 1-s windows   NORMAL / ELEVATED      LightGBM (+ IForest)   TreeSHAP      events.db        Streamlit
```

| Stage | File | In → Out | What to say about it |
|---|---|---|---|
| Prepare data (offline) | `ml/prepare.py` | 8 raw CSVs (~850 MB) → train/val/test parquet | "Cleaned infinities and duplicates, grouped 14 labels into 7 classes, removed port/IP so no leakage, 70/15/15 split." |
| Train (offline) | `ml/train.py` | train/val → `models/*` | "LightGBM on top 20 features, Isolation Forest on benign only with a 1% FPR threshold, RF baseline, benign percentiles for the sentences." |
| Replay | `pipeline/replayer.py` | scenario + `test.parquet` → one batch of flows per second | "Real test-set flows, never seen in training, replayed second by second following a script (benign, then DoS, then …)." |
| Tier 1 | `pipeline/monitor.py` | flow count → NORMAL / ELEVATED | "Cheap EWMA z-score on flow rate, with hysteresis." |
| Tier 2 | `pipeline/detector.py` | flows + state → flagged flows | "10% sample when NORMAL, everything with both models when ELEVATED." |
| Explain | `pipeline/explainer.py` | flagged flows → top 3 + sentences | "TreeSHAP built once at startup, top 3 features, compared with benign percentiles, cap 300 per window." |
| Store | `pipeline/store.py` | results → `data/events.db` | "SQLite in WAL mode so the dashboard can read while the pipeline writes." |
| Show | `dashboard/app.py` | DB → web page | "Streamlit refreshes every second." |
| Glue | `pipeline/run.py` | runs all the above every window | "The main loop." |

**Why replay instead of capturing real packets?** Replayed flows come with ground-truth labels, so we can prove whether each alert is right. The dashboard even shows the true label next to the prediction.

**Why SQLite + WAL?** The pipeline and dashboard are separate programs. SQLite is just a file, and WAL ("write-ahead log") mode lets one program write while the other reads without locking each other.

---

## 4. Tech stack

| Purpose | Tool | Why |
|---|---|---|
| Language | Python 3.11 | ML ecosystem; `shap` works best here |
| Data | pandas, numpy, pyarrow | Tables; parquet files are small and fast |
| Main model | LightGBM | Fast, accurate on table data, works with TreeSHAP |
| Other models | scikit-learn | Isolation Forest, Random Forest, metrics |
| Explanations | shap | TreeExplainer live; KernelExplainer only for the benchmark |
| Storage | SQLite (WAL), joblib | Zero-setup database; joblib saves models to disk |
| Dashboard | Streamlit + Plotly | Live web page in pure Python |
| Tests | pytest | 23 unit tests |
| Teamwork | GitHub, protected `main`, PRs | Each member owns folders; contracts frozen in `docs/PLAN.md` |

---

## 5. Setup (macOS)

You already have this. For a fresh laptop:

```bash
git clone https://github.com/krishitag/flowlens.git
cd flowlens
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install libomp          # LightGBM needs this on Mac
```

The trained models and the test data come with the clone; nothing else to download for the demo.

**Before the review (10 minutes ahead):**
```bash
cd ~/Desktop/flowlens
git checkout main && git pull
source .venv/bin/activate
```
- Open **two terminals**, both in the repo root, both with `.venv` active.
- Have the **backup video** open in another window.
- Turn off notifications. Charge the laptop.

**If something breaks:**

| Problem | Fix |
|---|---|
| Dashboard says "Waiting for the pipeline" | Start the pipeline from the repo root |
| Dashboard is white instead of dark | Start Streamlit from the repo root |
| LightGBM import error | `brew install libomp` |
| Results tab says "not available yet" | Click **Reload reports** |
| Anything weird during the live demo | Switch to the backup video. Don't debug in front of her |

---

## 6. The demo, step by step (about 10 minutes)

Each step: **command → what you'll see → what it means.**

### 6.1 Tests pass (30 seconds)

```bash
pytest tests/ -q
```
**Expected:** `23 passed` in ~5 seconds (ignore the yellow warnings, they're from the shap library).
**What it means:** the Tier-1 state machine, the percentile sentences and the explanation cap all behave as designed. Details in section 7.

### 6.2 Start the dashboard (Terminal 1)

```bash
streamlit run dashboard/app.py
```
**Expected:** a browser opens at http://localhost:8501 showing "Waiting for the pipeline". Full screen, zoom 110–125%.
**What it means:** the dashboard is a separate program; it only reads `data/events.db`.

### 6.3 Start the live run (Terminal 2)

```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```
**Expected:** Terminal 2 prints one line per second, like:
```
ts=   40  ELEVATED  z=  57.73  flows= 394  scored= 394  alerts= 280  explained= 280
```
The script `scenarios/demo.json` is: **benign 30 s → DoS 20 s → benign 20 s → PortScan 15 s → benign 20 s** (105 s total). `--speed 1` = real time.

**What to say as it runs:**

| Time | On screen | Say |
|---|---|---|
| 0–30 s | Green **NORMAL**, ~40 flows/s, coverage ~10% | "Normal traffic. Tier 1 only watches the flow rate. Tier 2 scores a 10% sample, so we don't waste compute." |
| ~30 s | Flows jump to ~400/s, z-score shoots past the red line | "A DoS attack starts. The z-score goes above 3…" |
| ~32 s | Red **ELEVATED**, shaded band, coverage 100% | "…3 windows in a row, so we go ELEVATED. Now every flow goes through LightGBM **and** Isolation Forest." |
| 32–50 s | Alerts table fills, Alerts-by-type shows DoS | Go to 6.4 |
| ~53 s | Back to green **NORMAL** | "Attack's over. 5 calm windows and we drop back to sampling." |
| ~72–88 s | ELEVATED again, PortScan alerts | "A port scan. Different attack, so different features explain it." Show one PortScan alert (6.4 again) |
| ~105 s | **RUN COMPLETE** | Point at the sidebar (6.5) |

### 6.4 Explain one alert (during the DoS part)

1. In the sidebar, switch on **Pause live updates** (freezes the screen).
2. In **Recent alerts**, pick a DoS row and note its ID.
3. In **Why was it flagged?**, type the ID.
4. Walk through the bar chart (each bar = one feature's SHAP push toward "attack") and the 3 sentences.
5. Point at the **true label** column: "We show ground truth so you can see it's actually right."
6. If there's a row with **⚠**: "The two models disagreed, so we mark it low confidence."
7. Switch **Pause** off.

**What to say:** "This is the reason, in plain language, computed in under a millisecond. With Kernel SHAP it would be about 2 seconds for *this one* flow, and we had ~400 flows a second."

### 6.5 Sidebar after the run

**Expected:** detect latency per flow (hundredths of a millisecond), explain latency per flow (~0.5 ms), % scored and explained per state.
**Numbers from our demo run:** 13,913 flows replayed. In NORMAL, 373 of 3,695 flows scored (**~10%**). In ELEVATED, all 10,218 scored. **6,550 alerts, 6,533 explained (99.7%)**.
**What it means:** that's the compute saving from tiering, and nearly every alert got its reason.

### 6.6 Results tab

**Show in this order:**
1. **TreeSHAP vs Kernel SHAP** chart: "2.4 ms vs ~2–2.6 s, ~800–1,100× faster. This is the core claim."
2. **Per-class F1:** "Macro F1 0.972. DoS, DDoS, PortScan, BruteForce are almost perfect. WebAttack 0.86 is the weakest; it's the smallest class and looks like normal web browsing."
3. **Leave-one-attack-out:** "We trained without DoS at all, then showed it DoS. LightGBM caught 5%, Isolation Forest 33%, together 37.8%. That's why we keep both models. Bot: 0%. That's a limitation."
4. **Pipeline latency:** "At ~1,100 flows per second, 95% of windows finished in 223 ms, well inside the 1-second budget."

### 6.7 (Optional) Prove the numbers are re-computable

```bash
python ml/evaluate.py
```
**Expected (~30 s):** per-class F1 for LightGBM and RF, `lgbm: macro F1 0.9719, benign FPR 0.0037`, `rf: macro F1 0.9856`.
**What it means:** the accuracy numbers come from a script anyone can rerun, not from a slide.

```bash
python -m pipeline.latency_report --scenario scenarios/stress.json
```
**Expected (~1 min):** ~100 windows at ~1,100 flows/s; end-to-end per window p95 ≈ 220 ms; % scored/explained per state.
**What it means:** the system keeps up with 25× the demo's normal traffic.

> Both rewrite files in `reports/` with tiny timing differences. Afterwards: `git checkout -- reports/`

### 6.8 (Optional) Show the limitation honestly

```bash
python -m pipeline.run --scenario scenarios/slowscan.json --speed 0
```
**Expected (a few seconds):** every line says **NORMAL**; only ~15–17 alerts in total.
**What it means:** a slow port scan hidden in normal traffic never raises the flow rate enough to trigger ELEVATED, so only the 10% sample catches it. "This is the trade-off of tiering, and we report it instead of hiding it."

### 6.9 (Optional) Show the raw data behind the dashboard

After any run:
```bash
sqlite3 data/events.db "SELECT id, true_label, pred_label, source, explanation FROM alerts WHERE pred_label='PortScan' LIMIT 2;"
```
**Expected:** alert rows with their real 3-line explanations. The first row may well be a **false alarm** (true label BENIGN, predicted PortScan). That's fine to show: "A normal flow that happened to look like a scan, and the explanation shows why: it was only 39 microseconds long. Our false alarm rate is 0.37%."
**What it means:** the dashboard isn't faking anything; it's reading this table.

### Don't run during the review

| Command | Why not |
|---|---|
| `python ml/train.py` | Overwrites the real models in `models/` |
| `python tests/make_fake_models.py` | Overwrites models and test data with fake ones |
| `python ml/benchmark_explain.py` | Takes ~6 minutes. Show `reports/figures/shap_latency.png` instead |
| `python ml/holdout.py` | Retrains models, slow. Show `reports/holdout.json` instead |

---

## 7. How the tests work and what they prove

We test the parts where a silent bug would make the demo **look** right but **be** wrong: the state machine, the sentence wording, and which alerts get explained under load. 23 tests, all passing.

| File | Tests | What they prove |
|---|---|---|
| `tests/test_monitor.py` | 7 | Tier 1 behaves exactly as designed |
| `tests/test_explainer.py` | 9 | The percentile sentences are correct |
| `tests/test_explain_cap.py` | 5 | The 300-per-window cap explains the right alerts |

**Example 1: Tier 1 flips after exactly 3 windows** (`tests/test_monitor.py`)
```python
def test_sustained_spike_flips_after_3_windows():
    m = warmed_up()                     # 30 windows of ~40 flows
    assert states(m, [CALM * 10] * 5) == ["NORMAL", "NORMAL", "ELEVATED", "ELEVATED", "ELEVATED"]
```
Feed calm traffic, then 10× traffic for 5 windows. The state must stay NORMAL twice and flip on the **3rd**.

**Example 2: an attack doesn't become the new normal**
```python
def test_baseline_not_learned_while_elevated():
    m = warmed_up()
    mean_before = m.mean
    states(m, [CALM * 10] * 50)        # 50 seconds of attack
    assert m.mean == mean_before       # the "normal" average didn't move
```

**All 7 monitor tests:** steady traffic stays NORMAL · sustained spike flips after 3 · back to NORMAL only after 5 calm windows · one spike during recovery resets the calm count · a single spike doesn't flip · nothing flips during warm-up · baseline frozen while ELEVATED.

**Explainer tests:** "above 99.9%", "below every normal flow", "above X%", "below X%", "typical, percentile X" all produced at the right values · many tied zeros (common in network data) aren't wrongly called "above"/"below" · on/off flags handled · sentence format is `Name = value (where)`.

**Cap tests:** under 300, everything is explained · over 300, LightGBM alerts go first by confidence, then Isolation-Forest-only by most anomalous · cap 0 and empty windows don't crash.

**Why the tied-zeros test matters:** network data is full of identical values (most flows have 0 PSH flags, for example). A naive percentile lookup would call a 0 "above 60% of normal flows", which is misleading. The explainer says "same value as about X% of normal flows" instead, and the test locks that in.

---

## 8. Results (all from real data)

| What | Result |
|---|---|
| Explanation time per flow | **TreeSHAP 2.4 ms vs Kernel SHAP ~2–2.6 s → ~800–1,100× faster** |
| Accuracy (test set, 69,487 flows) | Macro F1 **0.972** (LightGBM), 0.986 (Random Forest) |
| False alarms on normal traffic | **0.37%** |
| Strong classes | DoS, DDoS, PortScan, BruteForce ≥ 0.998 F1 |
| Weak classes | **WebAttack 0.86**, Bot 0.95 (the two smallest) |
| Never-seen DoS (held out of training) | **37.8%** caught (Isolation Forest 33%, LightGBM 5%) |
| Never-seen Bot | 0% caught |
| Under stress (~1,100 flows/s) | **223 ms** per 1-second window at p95 |
| Live demo | 6,550 alerts, **99.7% explained** |

**"RF scores higher, why use LightGBM?"** Predicting one flow takes ~0.34 ms with LightGBM vs ~14 ms with RF (~40× slower), and TreeSHAP on a big RF is slower too. For a live system, speed matters as much as 1.4 F1 points.

---

## 9. Novelty, advantages, limitations

### What's new

1. **Live explanations, not offline.** Most explainable-IDS papers explain afterwards with Kernel SHAP. We explain every alert as it happens.
2. **Measured speed-up.** TreeSHAP vs Kernel SHAP on the same models: ~800–1,100×.
3. **Two-tier compute saving.** Heavy work only when traffic looks abnormal.
4. **Known + unknown attacks.** Supervised + unsupervised model together, with a "low confidence" flag when they disagree.
5. **Human sentences.** SHAP numbers turned into "above 99% of normal flows".
6. **Bounded latency.** A per-window explanation budget keeps every second inside its 1-second deadline.

### Advantages

- Analyst sees **why**, not just **what**
- Fast enough for live traffic, with proof
- Saves compute when things are quiet
- Catches some never-seen attacks (Isolation Forest)
- No leakage: port, IP, flow ID, timestamps excluded
- Reproducible: clone, install, run; fixed random seeds

### Limitations (say these before she asks)

| Limitation | Why it happens | How it could be fixed |
|---|---|---|
| **Slow attacks** slip past Tier 1 | Tier 1 only watches **total** volume; a slow scan barely changes it | Add per-destination counters (e.g. "distinct ports per source") to Tier 1 |
| **Attacks that look normal** (Bot: 0% when unseen) | Isolation Forest at 1% FPR only catches clearly weird flows | Better unsupervised model, or accept more false alarms |
| **WebAttack F1 0.86** | Only 321 test flows, and they look like normal web browsing | More data; features from HTTP content |
| **Replayed, not live-captured** | We start from CSV rows, not packets | Add CICFlowMeter to turn live packets into flows |
| **Unexplained alerts under extreme load** | Above 300 alerts in one second, the least confident are stored without a reason | Bigger budget or more CPU |
| **One dataset from 2017** | One lab network | Test on CIC-IDS2018 / UNSW-NB15 |

---

## 10. Which files to know for Review 3

| Member | Files | Be ready to explain |
|---|---|---|
| **Krishita** (pipeline + ML) | `pipeline/run.py`, `monitor.py`, `detector.py`, `explainer.py`, `ml/prepare.py`, `ml/train.py`, `ml/benchmark_explain.py`, `tests/` | EWMA + z-score + hysteresis · 10% vs 100% scoring · flag rule · TreeSHAP + percentile sentences · explanation cap · leakage removal · why 20 features · how the benchmark was run |
| **Krish** (dashboard + paper) | `dashboard/app.py`, `dashboard/results.py`, `paper/paper.md` | How the dashboard reads the DB every second · each panel · low-confidence rule · Results tab |
| **Vedika** (first ML version, paper, slides) | `ml/evaluate.py`, `ml/holdout.py`, `reports/`, slides | F1 / FPR / confusion matrix · leave-one-attack-out test · reading the result figures |
| **Everyone** | `docs/PLAN.md`, `contracts/schema.sql`, `REVIEW3.md` | The problem, the claim, the architecture, the limitations |

---

## 11. Questions she may ask

**What problem are you solving?**
ML intrusion detectors give a label but no reason, and the usual way to get reasons (Kernel SHAP) is too slow for live traffic. We give a reason for every alert in real time.

**What's novel?**
Explanations live instead of offline, a measured ~800–1,100× speed-up from TreeSHAP, and a two-tier design that does heavy work only when traffic looks abnormal.

**Why not deep learning?**
Tree models are very accurate on table-style flow features, fast to run, and TreeSHAP gives *exact* explanations in milliseconds. Deep models would need slow approximate explainers, which defeats the purpose.

**Why two models?**
They do different jobs. LightGBM names known attacks. Isolation Forest only learned normal traffic, so it flags anything unusual. On never-seen DoS, LightGBM caught 5%, Isolation Forest 33%.

**What is a z-score / EWMA?**
EWMA is a running average where recent seconds count more. The z-score says how many standard deviations the current second is above that average. Above 3 is very unusual.

**Why 3 windows to enter and 5 to leave?**
So one noisy second doesn't trigger an alert, and the state doesn't flicker on and off during an attack. (We originally used 10 calm windows with z < 1, but with realistic random traffic it often never returned to NORMAL, so we changed it.)

**Why 10% sampling? Doesn't that miss attacks?**
In normal times, yes, we only see 10%. That's the trade-off, and it's exactly the slow-scan limitation. Once traffic jumps, we see 100%.

**97% F1, is that too good? Any leakage?**
We removed destination port, IPs, flow ID and timestamps, and dropped duplicate rows before splitting so the same flow can't be in both train and test. 0.97 is in line with published CIC-IDS2017 work, and WebAttack at 0.86 shows it isn't trivially perfect. Leakage usually shows up as > 99.5%.

**Why is it "real time" if it's a replay?**
Each 1-second window is processed exactly as live traffic would be, and has to finish within 1 second. Replaying lets us check every alert against the true label. Packet capture is the missing piece, listed as a limitation.

**The benchmark says 2.4 ms but the dashboard shows ~0.5 ms. Why?**
The benchmark times one flow at a time. The pipeline explains a whole second's flagged flows in one batch, which is cheaper per flow.

**How did you measure Kernel SHAP?**
`ml/benchmark_explain.py`: the same LightGBM model, Kernel SHAP with 100 benign flows as background, on 50 flagged flows (it's too slow for more), repeated 3 rounds, vs TreeSHAP on 200 flagged flows. TreeSHAP median 2.43 ms; Kernel SHAP median ~2.6 s. We report the speed-up as a range (~801–1,080×) because Kernel SHAP's time varies between rounds.

**What does an alert explanation actually look like?**
Real one: *"Flow Duration = 36 (below 92% of normal flows)"*, a port scan that knocked and left in 36 microseconds.

**What's "low confidence"?**
Both models looked at the flow but only one flagged it. We show ⚠ so the analyst knows to check.

**What happens if 1,000 attacks arrive in one second?**
All are detected and stored. Only the 300 most confident are explained; the rest are stored with "not explained: budget reached", so the window still finishes inside 1 second.

**What's the dataset?**
CIC-IDS2017 from the Canadian Institute for Cybersecurity: 5 days of a lab network with real attacks, already turned into flows with ~78 features each. We used the 8 CSVs, ~850 MB.

**What changed since Review 2?**
*(Fill in with the feedback you acted on.)* What's complete now: real models, the explanation cap, the full paper with real numbers, and a README that lets anyone clone and run it.

**What would you do next?**
Live packet capture with CICFlowMeter, a per-destination Tier-1 check to catch slow scans, and testing on newer datasets.

---

## 12. Cheat sheet (last 5 minutes before the review)

- **Flow** = one network conversation. **Feature** = one measurement of it. We use **20**.
- **Top 3 features** = the 3 that pushed *this* alert most, found by **SHAP**. Change per alert.
- **TreeSHAP 2.4 ms vs Kernel SHAP ~2 s → ~800–1,100× faster.** ← headline
- **Tier 1** = EWMA z-score on flow rate. ELEVATED after 3 windows z > 3; NORMAL after 5 windows z < 2.
- **Tier 2** = NORMAL: LightGBM on 10%. ELEVATED: LightGBM + Isolation Forest on 100%.
- **Cap** = max 300 explanations per second → p95 223 ms per window under stress.
- **Macro F1 0.972**, false alarms **0.37%**, WebAttack weakest (0.86).
- **Never-seen DoS: 37.8% caught**; never-seen Bot: 0%.
- **Demo:** 6,550 alerts, 99.7% explained.
- **Main limitation:** slow attacks don't trigger Tier 1.
- **No leakage:** no port, IP, flow ID or timestamp as features.
