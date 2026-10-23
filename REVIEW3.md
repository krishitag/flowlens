# FlowLens: Explainable Real-Time Network Anomaly Detection

**Review 3 · Computer Networks, VIT**
**Team:** Krishita Gupta (pipeline and ML) · Krish Singh (dashboard and paper) · Vedika (first ML version, paper and slides)

> **How to use this file.** Read it top to bottom while presenting. Lines in a grey box that start with **Say:** are the words to speak. Everything else is backup detail for when the professor asks. Section 16 lists the viva questions we expect, and Section 17 is a one-page cheat sheet of every number.

---

## Contents

1. Opening pitch (30 seconds)
2. Problem statement
3. Our solution and what is new
4. Dataset
5. System structure (architecture)
6. ML algorithms used
7. Attack types: DoS, DDoS, PortScan, BruteForce, WebAttack, Bot
8. Results
9. Problems we found and how we fixed them
10. Limitations
11. Future work
12. Live demo, step by step
13. Testing and how to verify every number
14. Technology stack
15. Project folder structure
16. Viva questions and answers
17. Cheat sheet: every number on one page
18. Conclusion

---

## 1. Opening pitch (30 seconds)

> **Say:** "FlowLens is a network intrusion detection system that detects attacks in traffic as it arrives, and also explains *why* each connection was flagged, in plain language, on a live dashboard. Other work explains alerts offline, after the fact, using a slow method called Kernel SHAP that takes about two seconds per connection. We use tree models with TreeSHAP, which gives the exact explanation in about 2 milliseconds, roughly a thousand times faster. Together with a two-tier design that only does the heavy work when traffic looks abnormal, every alert can be explained live. On the CIC-IDS2017 dataset our model reaches a macro F1 of 0.987 with only 0.18% false alarms on normal traffic."

---

## 2. Problem statement

> **Say:** "Network monitoring tools keep *visibility* and *security* separate. A traffic dashboard shows volumes; a security tool raises alerts. When a machine-learning detector raises an alert, the analyst gets only a label like 'DoS', with no reason. So they can't tell a real attack from a false alarm, and they can't trust the detector enough to act on it."

- Research papers fix this with **SHAP**, a method that shows which inputs pushed a model toward its decision.
- But they explain **offline** and mostly use **Kernel SHAP**, which works with any model but is slow: about **2 seconds per connection** on our models.
- A busy network produces **hundreds to thousands of connections per second**, so Kernel SHAP cannot keep up.

> **Say:** "Our question was: can every alert be explained in real time, while the traffic is still arriving?"

---

## 3. Our solution and what is new

> **Say:** "We combine four ideas."

1. **Tree models with TreeSHAP.** TreeSHAP is the version of SHAP built for tree-based models. It uses the tree structure to compute the **exact** explanation instead of estimating it. On our model it takes **2.3 ms per connection**, about **800–1,100× faster** than Kernel SHAP. **This measured speed-up is the main result.**
2. **A two-tier design.** A cheap check (Tier 1) runs on every second of traffic. The expensive work (scoring every connection with both models and explaining the alerts) only happens when Tier 1 says traffic looks abnormal.
3. **Two complementary models.** **LightGBM** (supervised) names attack types it was trained on. **Isolation Forest** (unsupervised, trained only on normal traffic) flags anything unusual, including attacks it has never seen.
4. **Explanations a person can read.** Each alert lists its **top 3 features** compared with normal traffic, for example *"Flow Duration = 39 (below 91% of normal flows)"*.

> **Say:** "The novelty is not SHAP itself. It is making per-alert explanations **live**, and **measuring** that they fit inside a one-second budget."

---

## 4. Dataset

### 4.1 CIC-IDS2017

- Public dataset from the **Canadian Institute for Cybersecurity** (University of New Brunswick).
- **5 days** of traffic from a lab network (Monday to Friday, July 2017), with real attacks mixed into normal activity.
- It stores **flows**, not raw packets: one row per connection, with about **78 numbers** computed by a tool called **CICFlowMeter** (duration, packets and bytes each way, gaps between packets, TCP flags, window sizes).
- Every flow has a **label** (BENIGN or the attack name), so every alert can be checked against the truth.

### 4.2 Preparation (`ml/prepare.py`)

1. Loaded the 8 daily CSV files (~850 MB).
2. Removed rows with infinite or missing values, and **exact duplicate rows**, so the same flow cannot appear in both training and testing.
3. Grouped the 14 original labels into **7 classes**. Infiltration and Heartbleed were dropped: too few examples to learn from.
4. Split **70% train / 15% validation / 15% test**, keeping class proportions the same in each (stratified split).
5. Result: **324,268 train, 69,486 validation, 69,487 test** flows, 76 numeric features.

| Class | Test flows |
|---|---|
| BENIGN | 45,001 |
| DoS | 7,500 |
| DDoS | 7,500 |
| PortScan | 7,500 |
| BruteForce | 1,373 |
| WebAttack | 321 |
| Bot | 292 |

(After removing duplicates, normal traffic was capped at 300,000 flows and each attack class at 50,000 before splitting, so training stays fast; the small classes were kept whole.)

### 4.3 Feature selection

- Trained LightGBM on all 76 features, ranked them by **gain importance** (how much each feature improves the trees' splits), kept the **top 20**, retrained.
- Validation macro F1: **0.989 with 76 features → 0.987 with 20**. Only 0.2 points lost, but explanations are shorter and the model is faster.
- The 20 features: `Init_Win_bytes_backward`, `Flow Duration`, `Bwd Header Length`, `Total Length of Bwd Packets`, `Bwd Packet Length Min`, `Bwd IAT Min`, `PSH Flag Count`, `Fwd Header Length`, `Idle Mean`, `min_seg_size_forward`, `Idle Min`, `Fwd PSH Flags`, `Total Backward Packets`, `Init_Win_bytes_forward`, `Flow IAT Max`, `Total Length of Fwd Packets`, `Bwd Packet Length Std`, `Fwd IAT Max`, `Packet Length Std`, `act_data_pkt_fwd`.

**Meaning of the terms you will see:**

| Term | Meaning |
|---|---|
| Fwd / Bwd | Forward = client → server; Backward = server → client |
| IAT | Inter-arrival time: the gap between two packets |
| Flow Duration | How long the connection lasted (microseconds) |
| Init_Win_bytes | TCP window size in the first packet each way |
| PSH flag | TCP flag that says "deliver this data now" |
| min_seg_size_forward | Smallest TCP segment header the client sent |

### 4.4 Data leakage: what we deliberately left out

> **Say:** "We excluded the destination port, IP addresses, flow ID and timestamps from the features. In this dataset they give the answer away: every attack came from a few attacker IPs and at known times. A model using them would score almost perfectly here and fail on any other network. That is called data leakage."

---

## 5. System structure (architecture)

```
                   ┌──────────── offline (run once) ────────────┐
CIC-IDS2017 CSVs ──▶ prepare.py ──▶ train.py ──▶ models + baselines
                   └────────────────────────────────────────────┘
                                         │
                   ┌──────────── online (every second) ─────────┐
 scenario file ──▶ Replayer ──▶ Tier 1 ──▶ Tier 2 ──▶ Explainer ──▶ SQLite ──▶ Dashboard
                  (1-s windows) (monitor) (detector) (TreeSHAP)    (events.db) (Streamlit)
                   └────────────────────────────────────────────┘
```

> **Say:** "The system has two halves. The offline half prepares data and trains the models once. The online half replays test traffic the models have never seen, one second at a time, and passes each second through five stages."

### 5.1 Replayer (`pipeline/replayer.py`)

- A **scenario file** (JSON) describes the traffic: e.g. 30 s normal at 40 flows/s, then 20 s of DoS at 400 flows/s, and so on.
- For each second it samples real flows of that label from the **test set** and hands them on as one **window**.
- Attack segments can mix in normal traffic (`benign_mix`), so attacks are never "pure".

### 5.2 Tier 1: the quick check (`pipeline/monitor.py`)

- Counts flows in the current second and compares with the **EWMA** (exponentially weighted moving average, α = 0.1) of normal traffic.
- Computes a **z-score**: how many standard deviations this second is above normal.
- **NORMAL → ELEVATED** when z > 3 for **3 seconds in a row**.
- **ELEVATED → NORMAL** after **5 calm seconds in a row** (z < 2).
- The average only learns from calm seconds, so a long attack never becomes "the new normal".

> **Say:** "Using different rules to enter and leave — 3 seconds at z > 3 versus 5 seconds at z < 2 — stops the state from flickering because of one noisy second. This is called hysteresis."

### 5.3 Tier 2: the detailed check (`pipeline/detector.py`)

| State | What gets scored |
|---|---|
| NORMAL | LightGBM scores a random **10%** of flows |
| ELEVATED | LightGBM **and** Isolation Forest score **every** flow |

A flow becomes an **alert** if:
- LightGBM predicts an attack class with **≥ 50% probability**, **or**
- the Isolation Forest score is below its threshold (set so only **~1% of normal traffic** is flagged).

Each alert records **who flagged it**: `lgbm`, `iforest` or `both`. If both models scored a flow but only one flagged it, the dashboard marks it **low confidence**.

### 5.4 Explainer (`pipeline/explainer.py`)

1. **TreeSHAP** computes how much each of the 20 features pushed the model toward the predicted class (for Isolation Forest alerts: toward "anomalous").
2. The **3 largest** contributions are kept.
3. Each value is compared with the **percentiles of that feature in normal training traffic** (stored in `models/baselines.json`) and turned into a sentence: *"above 99% of normal flows"*, *"typical for normal flows, percentile 73"*, or *"same value as about 27% of normal flows"* (for values like 0 that many flows share).
4. The explainer is **built once at startup**, not per alert.
5. **Cap:** at most **300 alerts explained per second**, most confident first. Extra alerts are still stored, just without an explanation (see Fix 2 in Section 9).

### 5.5 Storage (`pipeline/store.py`, `contracts/schema.sql`)

- **SQLite** database `data/events.db`, 3 tables:
  - `traffic_windows`: one row per second (flows, packets, bytes, z-score, state, how many scored and explained)
  - `alerts`: one row per alert (predicted label, true label, probability, IForest score, source, top features, explanation, timings)
  - `run_meta`: one row per run
- **WAL mode** (write-ahead logging) lets the dashboard read while the pipeline writes, without blocking.

### 5.6 Dashboard (`dashboard/app.py`)

Streamlit, refreshes every second:
- **Status strip and KPI tiles:** current state (green NORMAL / red ELEVATED), z-score, flows/s, packets/s, alerts in the last 60 s, % of flows scored.
- **Traffic over time:** flow rate and z-score as two aligned panels, with the z = 3 and z = 2 lines and ELEVATED periods shaded.
- **Alerts:** the last 50 alerts with predicted and true labels; alerts by type.
- **Explanation panel:** the selected alert with SHAP bars, the 3 plain-language reasons and the low-confidence tag; Prev / Next / Latest buttons; Pause for presenting.
- **Sidebar:** detection and explanation latency (p50 / p95), % scored and explained per state.
- **Results tab:** the offline evaluation (Section 8).

---

## 6. ML algorithms used

> **Say:** "We use three models and two explanation methods. Here is what each one does and why we chose it."

### 6.1 EWMA z-score (Tier 1, statistics, not ML)

- **What:** a running average where recent seconds count more: `mean = 0.1 × current + 0.9 × old mean`. Same for variance. z = (current − mean) / std.
- **Why:** costs almost nothing, reacts within seconds, needs no training.

### 6.2 LightGBM (main classifier)

- **What:** **gradient-boosted decision trees**. It builds 200 small trees one after another; each new tree corrects the mistakes of the trees before it. The final answer adds up all the trees.
- **Leaf-wise growth:** it grows the branch that reduces error most, so it is accurate with few trees.
- **Histogram-based:** it sorts each feature's values into bins and only tries splits between bins, which makes it fast.
- **Our settings:** 200 trees, `class_weight='balanced'` (rare classes count more), **`max_bin=1023`** (finer bins, see Fix 1 in Section 9), 20 features, 7 output classes.
- **Why:** best accuracy-for-speed on tabular data; classifies a single flow in **0.36 ms**; supported **exactly** by TreeSHAP.

### 6.3 Isolation Forest (unknown-attack detector)

- **What:** an **unsupervised** model trained **only on normal traffic** (209,999 benign flows). It builds 100 random trees that keep splitting the data at random. **Unusual points get isolated in fewer splits**, so a short path length means "anomaly".
- **Threshold:** the 1st percentile of scores on normal validation flows (−0.674), so about **1% of normal traffic** is flagged (0.90% on test).
- **Why:** it never sees attack labels, so it can flag attack types the classifier was never trained on. It is also a tree ensemble, so TreeSHAP explains it too.

### 6.4 Random Forest (baseline only)

- **What:** 100 independent deep decision trees, each on a random sample of the data; they vote.
- **Why it is there:** a standard, strong baseline to compare against. **Not used live**, because a single-flow prediction takes **14 ms**, about **39× slower** than LightGBM.

### 6.5 SHAP, TreeSHAP and Kernel SHAP (explanations)

- **SHAP** comes from game theory (**Shapley values**): treat each feature as a "player" and fairly share out the model's output among them. A feature's SHAP value = its average contribution over all combinations of the other features.
- **Kernel SHAP:** works with **any** model. It estimates Shapley values by running the model on **many perturbed copies** of the input and fitting a weighted linear regression. Approximate, and slow: **~1.9–2.6 s per flow**.
- **TreeSHAP:** works only with **tree models**, but walks the trees directly and computes the **exact** Shapley values in polynomial time, with no sampling: **2.3 ms per flow** (≈ 0.5 ms per flow live, when a whole second's alerts are explained in one batch).

> **Say:** "Choosing tree models is what makes TreeSHAP possible, and TreeSHAP is what makes live explanation possible."

---

## 7. Attack types: DoS, DDoS, PortScan, BruteForce, WebAttack, Bot

> **Say:** "The explanations change with the attack, which is what we expect if they reflect real behaviour. Let me go through each attack."

Median values from the test set (durations in microseconds, µs):

| Class | Flow Duration | Longest gap between packets | Bytes client → server | Bytes server → client | Destination ports used |
|---|---|---|---|---|---|
| BENIGN | 46 ms | 32 ms | 68 | 145 | 8,450 |
| **DoS** | **85.8 s** | **85.4 s** | 352 | **11,595** | 1 (port 80) |
| **DDoS** | 2.0 s | 2.0 s | 26 | **11,601** | 2 |
| **PortScan** | **50 µs** | 50 µs | **0** | 6 | **997** |
| **BruteForce** | 9.1 s | 2.6 s | 106 | 188 | 3 (21 FTP, 22 SSH) |
| **WebAttack** | 5.5 s | 5.4 s | 0 | 0 | 1 (port 80) |
| **Bot** | 73 ms | 71 ms | 6 | 18 | 106 (mostly 8080) |

### 7.1 DoS (Denial of Service)

- **What:** **one** attacker machine overloads a web server so real users can't reach it. Tools in the dataset: **Hulk**, **GoldenEye**, **slowloris**, **slowhttptest**.
- **How it looks:** very long, heavy connections. Slowloris opens a connection and keeps it hanging for over a minute to tie up the server; Hulk floods it with requests, so the server sends back large responses.
- **Real explanation from our demo:** *"Bwd Packet Length Std = 1,762 (above 99.9% of normal flows)"*, *"Total Length of Bwd Packets = 11,595 (above 95% of normal flows)"*.
- **Result:** F1 **0.998**. In the demo it raises traffic volume, so Tier 1 goes ELEVATED within 3 seconds.

### 7.2 DDoS (Distributed Denial of Service)

- **What:** the same goal as DoS, but from **many machines at once** (the dataset uses the **LOIC** tool).
- **How it looks:** many short client packets (median 26 bytes sent) with large server replies (~11.6 KB).
- **Real explanation:** *"Total Length of Fwd Packets = 24 (percentile 25 of normal)"*, *"min_seg_size_forward = 20"*, *"Init_Win_bytes_forward = 256"*: a pattern of tiny, identical requests.
- **Result:** F1 **0.9995**, the best class.

### 7.3 PortScan

- **What:** the attacker probes **many ports** on a machine to find open services (the dataset uses **nmap**). It is reconnaissance before an attack.
- **How it looks:** tiny probes. Each touches a port and leaves within **microseconds**, sending **0 bytes** of data. 997 different ports in the test set.
- **Real explanation from our demo:** *"Flow Duration = 39 (below 91% of normal flows)"*, *"PSH Flag Count = 1"*.
- **Result:** F1 **0.998**.

> **Say:** "We detect port scans **without** using the port number as a feature. Each probe has a distinctive shape — almost zero duration and no data — and the model recognises that shape one connection at a time."

### 7.4 BruteForce

- **What:** repeatedly guessing **passwords** for **FTP** (port 21) and **SSH** (port 22) logins (the dataset uses **Patator**: FTP-Patator, SSH-Patator).
- **How it looks:** medium-length connections (~9 s) with a login exchange: a few hundred bytes each way, many header bytes from the server.
- **Real explanation:** *"Bwd Header Length = 1,140 (above 98% of normal flows)"*: the server sends many small packets (login prompts and "wrong password" replies).
- **Result:** F1 **0.999**.

### 7.5 WebAttack

- **What:** attacks on a website's application layer: **login brute force**, **XSS** (cross-site scripting: injecting JavaScript into a page) and **SQL injection** (injecting database commands into a form).
- **How it looks:** this is the hardest class, because the traffic is normal HTTP to port 80 and looks like browsing.
- **Real explanation:** *"Init_Win_bytes_backward = 28,960 (above 94% of normal flows)"*, *"Fwd IAT Max = 5,933,223 (percentile 84)"*.
- **Result:** F1 **0.96** (was 0.86 before Fix 1). Precision 0.94, recall 0.99.
- **Honest note:** the TCP window size 28,960 is a property of the lab's victim web server. That is a possible dataset artefact, which we mention under Limitations.

### 7.6 Bot (botnet)

- **What:** an infected machine (the dataset uses the **ARES** botnet) talking to its **command-and-control** server, mostly on port 8080, to receive commands and send data.
- **How it looks:** small, short, regular connections (~6 bytes out, 18 bytes back), very similar to normal traffic.
- **Real explanation:** *"Bwd Packet Length Std = 72.23 (percentile 77)"*, *"Init_Win_bytes_backward = 237"*, *"Total Length of Bwd Packets = 134"*.
- **Result:** F1 **0.95**. Weak when unseen (Section 8.3): flows look normal one at a time.

---

## 8. Results

All numbers come from the real CIC-IDS2017 **test set** (never used for training or tuning) and are produced by scripts in the repository.

### 8.1 Explanation speed (main result)

| Method | Median time per flow |
|---|---|
| Kernel SHAP | ~1.9–2.6 s (varies run to run) |
| **TreeSHAP** | **2.3 ms** |
| TreeSHAP live, batched per second | ~0.5 ms |

> **Say:** "TreeSHAP is about **800 to 1,100 times faster**. We give a range because Kernel SHAP's time varied across three rounds of measurement; our latest run measured 844–990×."

### 8.2 Detection accuracy

| Model | Macro F1 | Accuracy | False alarms on normal traffic | Time for one flow |
|---|---|---|---|---|
| **LightGBM** (used live) | **0.987** | **99.84%** | **0.18%** | **0.36 ms** |
| Random Forest (baseline) | 0.986 | — | 0.15% | 14 ms |

Per-class F1 (LightGBM):

| BENIGN | DoS | DDoS | PortScan | BruteForce | WebAttack | Bot |
|---|---|---|---|---|---|---|
| 0.999 | 0.998 | 0.9995 | 0.998 | 0.999 | **0.964** | **0.949** |

- **Macro F1** = the average F1 over the 7 classes, so the small classes count as much as the big ones. That is why we report it instead of accuracy alone (accuracy is dominated by BENIGN, which is 65% of the test set).
- LightGBM now **matches** Random Forest on accuracy and is **~39× faster** per flow, so it is the clear choice for live use.

### 8.3 Attacks never seen during training (leave-one-attack-out)

We retrained LightGBM **without** one attack class, then checked how many of that class's flows were still caught.

| Held-out attack | LightGBM alone | Isolation Forest alone | Either |
|---|---|---|---|
| DoS | 4.4% | 47.8% | **51.6%** |
| Bot | 0% | 0% | 0% |

> **Say:** "This is why we use two models. LightGBM almost completely misses a DoS attack it never saw — it calls 96% of those flows normal. The Isolation Forest, which only knows what normal looks like, still catches about half of them. Bot is different: its flows look normal one at a time, so neither model catches it when unseen."

### 8.4 Real-time performance (stress test: ~1,100 flows/s average, ~1,560 flows/s during attacks)

| Measure | Result |
|---|---|
| Time per 1-second window (p95) | **186–225 ms** over 3 runs (budget 1,000 ms) |
| Same, without the explanation cap | 976–1,245 ms (at or over budget) |
| Detection time per flow | ~0.013 ms |
| Explanation time per flow (batched) | ~0.46 ms |
| Flows scored in NORMAL / ELEVATED | 10% / 100% |
| Demo run | 6,538 alerts, **6,521 explained (99.7%)** |

---

## 9. Problems we found and how we fixed them

> **Say:** "Along the way we hit several problems. Here is each one, what caused it and how we fixed it."

### Fix 1: WebAttack false alarms (accuracy fix)

- **Problem:** WebAttack F1 was only **0.86**. It caught 99% of web attacks, but **98 normal flows** were also labelled WebAttack (precision 0.76).
- **What we tried first:** softer class weights, more trees, more leaves. **None made any difference** (all stayed at 0.85 on validation).
- **Cause:** LightGBM sorts each feature into only **255 bins** by default. That is too coarse: the values that separate web attacks from normal browsing fell inside the same bin.
- **Fix:** **`max_bin=1023`** (one line in `ml/train.py`). We chose it on the **validation** set, not the test set. 16,383 bins made training unstable, so we stayed at 1,023.
- **Result (test set):**

| | Before | After |
|---|---|---|
| Macro F1 | 0.972 | **0.987** |
| WebAttack F1 | 0.86 | **0.96** |
| Normal flows wrongly called WebAttack | 98 | **18** |
| False alarms on normal traffic | 0.37% | **0.18%** |
| Unseen DoS caught | 37.8% | **51.6%** |

### Fix 2: Too slow under heavy load (explanation cap)

- **Problem:** under heavy attack (~1,560 flows/s), explaining **every** alert took ~700 ms per second, and the full window reached **~1,000–1,250 ms**: over the 1-second budget, so the system would fall behind.
- **Fix:** explain at most **300 alerts per second**, **most confident first** (LightGBM alerts by probability, then Isolation Forest-only alerts by anomaly score). The rest are stored with their prediction but marked *"Not explained: per-window explanation budget reached"*.
- **Result:** p95 **186–225 ms per window**; the demo still explains **99.7%** of alerts.

### Fix 3: Data leakage

- **Problem:** with destination port, IPs and timestamps as features, the model could "cheat": all attacks come from known IPs at known times.
- **Fix:** removed them from the features; removed exact duplicate rows **before** splitting so the same flow can't be in train and test.

### Fix 4: The monitor learning the attack as "normal"

- **Problem:** if the EWMA keeps updating during a long attack, the attack becomes the new average and the state drops back to NORMAL mid-attack.
- **Fix:** the average only learns from calm seconds; enter/exit use different rules (hysteresis). Covered by `tests/test_monitor.py`.

### Fix 5: Misleading explanation wording

- **Problem:** many features are 0 for most flows. Saying "value 0 is above 40% of normal flows" is misleading.
- **Fix:** for tied values the sentence says *"same value as about 27% of normal flows"*. Covered by `tests/test_explainer.py`.

### Fix 6: Honest reporting of the speed-up

- **Problem:** Kernel SHAP's time varies between runs, so a single number like "1,000×" would be misleading.
- **Fix:** we measure over 3 rounds and report a **range (800–1,100×)**. The dashboard's latency statistics also only count alerts that were actually explained (`explain_ms > 0`), so cap-skipped alerts don't make it look faster.

---

## 10. Limitations

> **Say:** "These are the limitations we know about, and we measured each one."

1. **Slow, low-volume attacks.** Tier 1 watches total traffic **volume**. Our `slowscan` scenario adds only ~5 scan flows per second to 40 normal ones, which never raises the z-score enough, so the system **stays NORMAL throughout** and only the 10% sample catches it (**15 PortScan alerts**). This is the direct trade-off of the two-tier design.
2. **Unseen attacks that look normal.** With Bot held out of training, **0%** was caught by either model.
3. **Small classes.** WebAttack has only 321 test flows and Bot 292, so their scores are less certain than the big classes'.
4. **Dataset artefacts.** CIC-IDS2017 comes from one lab network in 2017, and later studies found labelling errors in it. Some features (e.g. the web server's TCP window size for WebAttack) may be specific to that lab. Results on a real network would likely be lower.
5. **Replayed, not captured, traffic.** We replay recorded flows; our timings do not include packet capture and flow extraction.
6. **Explanation cap.** Above 300 alerts in one second, the least confident alerts get no explanation. In the demo that was 17 of 6,538.
7. **True labels on the dashboard.** We show the true label so the demo is honest about mistakes; a real deployment would not have it.
8. **No user study.** We measured how **fast** explanations are, not how much they **help** an analyst.

---

## 11. Future work

- **Live capture:** run CICFlowMeter on live packets instead of replaying recorded flows.
- **Catch slow scans:** add a per-source check to Tier 1 that counts how many different ports each machine contacts.
- **Better unseen-attack detection:** behaviour of a host **over time**, not single flows (would help with Bot).
- **More datasets:** CSE-CIC-IDS2018, UNSW-NB15, to test generalisation.
- **User study:** measure whether explanations make analysts faster or more accurate.

---

## 12. Live demo, step by step

**Before the review:** open two terminals in the project folder, activate the environment (`source .venv/bin/activate`).

**Terminal 1** (dashboard, opens at http://localhost:8501):
```bash
streamlit run dashboard/app.py
```

**Terminal 2** (pipeline, ~105 seconds):
```bash
python -m pipeline.run --scenario scenarios/demo.json --speed 1
```

| Time | Traffic | What happens | What to say |
|---|---|---|---|
| 0–30 s | Normal, 40 flows/s | Green **NORMAL**; only 10% of flows scored | "Quiet network. Tier 1 is learning what normal looks like; Tier 2 only samples 10%." |
| 30–50 s | **DoS**, 400 flows/s (30% normal mixed in) | z-score jumps; at ~32 s state turns red **ELEVATED**; every flow scored; DoS alerts appear | "Volume jumped. After 3 high seconds we go ELEVATED and score everything." Click a DoS alert: "It was flagged because the server sent back far more data than 95% of normal flows." |
| 50–70 s | Normal | After 5 calm seconds (~53 s), back to **NORMAL** | "Five calm seconds and we drop back, so the system doesn't flicker." |
| 70–85 s | **PortScan**, 200 flows/s (50% normal) | **ELEVATED** again (~72–88 s); PortScan alerts | Click a PortScan alert: "Different reason this time: duration of 39 microseconds, shorter than 91% of normal flows. The explanation matches the attack." |
| 85–105 s | Normal | Back to **NORMAL** | Point at the sidebar: "Detection and explanation latency, and the share of flows scored in each state." |

**After the run:** open the **Results** tab and show the TreeSHAP vs Kernel SHAP chart, per-class F1, the unseen-attack table and the latency numbers.

**If something breaks:** close and rerun Terminal 2; the dashboard survives the database being recreated.

---

## 13. Testing and how to verify every number

```bash
pytest tests/ -q
```

**23 unit tests, all passing.** They cover the parts where a silent bug would make the demo look right while being wrong:

| Test file | What it checks |
|---|---|
| `test_monitor.py` | Tier 1 turns ELEVATED after exactly 3 abnormal seconds, ignores a single spike, returns to NORMAL only after 5 calm seconds, and doesn't learn the attack as normal |
| `test_explainer.py` | The sentences use the right percentile wording, including tied values like 0 |
| `test_explain_cap.py` | Under heavy load, the 300 most confident alerts are explained first; edge cases (no alerts, cap of 0) work |

Every number in Section 8 is recomputed by a script:

| Command | Recomputes |
|---|---|
| `python ml/train.py` | Trains all models (~30 s) |
| `python ml/evaluate.py` | Accuracy, macro F1, per-class F1, confusion matrix |
| `python ml/holdout.py` | Unseen-attack test |
| `python ml/benchmark_explain.py` | TreeSHAP vs Kernel SHAP speed |
| `python -m pipeline.latency_report --scenario scenarios/stress.json` | Real-time performance |

---

## 14. Technology stack

| Purpose | Technology |
|---|---|
| Language | Python 3.11 |
| Data | pandas, NumPy, PyArrow (Parquet files) |
| Machine learning | LightGBM, scikit-learn (Isolation Forest, Random Forest, metrics) |
| Explanations | SHAP (`TreeExplainer` live; `KernelExplainer` only for the benchmark) |
| Storage | SQLite in WAL mode; joblib for saved models |
| Dashboard | Streamlit and Plotly |
| Testing | pytest |
| Collaboration | GitHub: protected `main`, pull requests with one approval |

---

## 15. Project folder structure

| Folder | Contents |
|---|---|
| `ml/` | `prepare.py` (data), `train.py`, `evaluate.py`, `holdout.py` (unseen attacks), `benchmark_explain.py` (SHAP speed) |
| `models/` | Trained models, the 20 features, class labels, Isolation Forest threshold, normal-traffic percentiles |
| `pipeline/` | `replayer.py`, `monitor.py` (Tier 1), `detector.py` (Tier 2), `explainer.py`, `store.py`, `run.py` (main loop), `latency_report.py` |
| `dashboard/` | Streamlit live dashboard and Results tab |
| `scenarios/` | `demo.json`, `stress.json` (heavy load), `slowscan.json` (limitation) |
| `tests/` | Unit tests |
| `reports/` | Results JSON files and figures |
| `contracts/` | Database schema shared by pipeline and dashboard |
| `paper/` | Project report |

---

## 16. Viva questions and answers

**Q: What is the novelty? SHAP already exists.**
A: SHAP exists, but published intrusion-detection work uses it offline, mostly with Kernel SHAP at seconds per flow. We show that tree models + TreeSHAP + a two-tier design make per-alert explanation fit inside a one-second window, and we **measured** it: ~800–1,100× faster, 186–225 ms per window at p95.

**Q: Why LightGBM and not deep learning?**
A: Flow data is tabular; gradient-boosted trees are the strongest models for tabular data. Trees also allow **exact** TreeSHAP explanations in milliseconds. A neural network would need Kernel SHAP or approximations, which is exactly the slowness we avoid.

**Q: Why not Random Forest? It is a tree model too.**
A: It reaches the same accuracy (0.986 vs our 0.987) but takes 14 ms per flow vs 0.36 ms, about 39× slower, and its deep trees make TreeSHAP slower as well.

**Q: What is the difference between TreeSHAP and Kernel SHAP?**
A: Kernel SHAP treats the model as a black box and estimates Shapley values by running it on many perturbed inputs: approximate and slow. TreeSHAP reads the tree structure and computes the exact values in polynomial time, with no sampling.

**Q: What are Shapley values?**
A: From game theory: a fair way to share a total payout among players. Here the "payout" is the model's output and the "players" are features. A feature's value is its average marginal contribution over all subsets of the other features.

**Q: Why two models?**
A: LightGBM only knows attacks it was trained on. Isolation Forest only knows normal traffic, so it flags anything unusual. With DoS held out, LightGBM alone caught 4.4%, the two together 51.6%.

**Q: How does Isolation Forest work?**
A: Random trees split the data at random points. Anomalies are few and different, so they get isolated in fewer splits. A short average path length means anomaly.

**Q: How did you pick the Isolation Forest threshold?**
A: The 1st percentile of its scores on normal validation flows, so ~1% of normal traffic is flagged (0.90% on test). A lower threshold would catch more attacks but raise more false alarms.

**Q: Why the two-tier design?**
A: Scoring and explaining everything all the time wastes compute when the network is quiet. Tier 1 is almost free; full work only runs when traffic is abnormal. The cost is that slow, low-volume attacks can slip past Tier 1 (our slowscan limitation).

**Q: What is EWMA and why z > 3?**
A: An exponentially weighted moving average: recent seconds count more. z = 3 means three standard deviations above normal, very unlikely by chance. Requiring 3 seconds in a row avoids reacting to one spike.

**Q: Why did you remove the port and IP? Isn't the port useful?**
A: In this dataset, attacks came from a few known IPs and specific ports, so the model would learn "this IP = attack" instead of attack behaviour. That would not work on another network. We still detect port scans from the shape of each probe.

**Q: How did you fix WebAttack?**
A: Class weights, more trees and more leaves changed nothing. The cause was LightGBM's default of 255 histogram bins per feature: too coarse. With 1,023 bins, WebAttack F1 went from 0.86 to 0.96 and false alarms on normal traffic halved (0.37% → 0.18%). We tuned on the validation set, not the test set.

**Q: Isn't 99.84% accuracy suspicious?**
A: Accuracy is inflated because 65% of flows are normal, which is why we report macro F1 (0.987). CIC-IDS2017 is a lab dataset with known artefacts, so real-network performance would likely be lower; we say this under Limitations. We also removed leakage features and duplicates.

**Q: What happens if there are more than 300 alerts in a second?**
A: The 300 most confident are explained; the rest are stored as alerts without an explanation. Without the cap the system went over budget (976–1,245 ms per window); with it, 186–225 ms.

**Q: Why SQLite and WAL mode?**
A: SQLite needs no server and is enough for one writer and one reader. WAL mode lets the dashboard read while the pipeline writes without either blocking.

**Q: How do you know the explanations are correct?**
A: TreeSHAP's values are exact for the model, not estimates. We also checked that the Isolation Forest's SHAP values track its anomaly score (correlation 0.994), and the explanations differ by attack in ways that match how the attacks work (long gaps for DoS, microsecond durations for PortScan).

**Q: What would you change for a real deployment?**
A: Live capture with CICFlowMeter, a per-source port counter to catch slow scans, retraining on the target network's own traffic, and a user study of the explanations.

**Q: Why is the slow scan missed?**
A: It adds only ~5 flows per second to ~40 normal ones; the volume barely changes, so Tier 1 never goes ELEVATED and only the 10% sample scores it. That is the trade-off of tiering by volume.

---

## 17. Cheat sheet: every number on one page

| Item | Number |
|---|---|
| Dataset | CIC-IDS2017, 5 days, 7 classes |
| Split | 324,268 train / 69,486 val / 69,487 test |
| Features | 76 → **20** (val macro F1 0.989 → 0.987) |
| LightGBM | 200 trees, balanced weights, `max_bin=1023` |
| **Macro F1** | **0.987** (RF 0.986) |
| **Accuracy** | **99.84%** |
| **False alarms (normal)** | **0.18%** (was 0.37%) |
| WebAttack F1 | **0.96** (was 0.86) |
| Bot F1 | 0.95 |
| Others F1 | ≥ 0.998 |
| One-flow prediction | LightGBM 0.36 ms vs RF 14 ms (~39×) |
| **TreeSHAP** | **2.3 ms/flow** (0.5 ms batched live) |
| Kernel SHAP | ~1.9–2.6 s/flow |
| **Speed-up** | **~800–1,100×** |
| Isolation Forest | 100 trees, 1% normal FPR (0.90% test) |
| Unseen DoS caught | LightGBM 4.4%, IForest 47.8%, **either 51.6%** |
| Unseen Bot caught | 0% |
| Tier 1 | EWMA α = 0.1; ELEVATED at z > 3 × 3 s; NORMAL at z < 2 × 5 s |
| Tier 2 | 10% sampled in NORMAL, 100% in ELEVATED |
| Explanation cap | 300 per second |
| **Window time p95 (stress)** | **186–225 ms** (budget 1,000; uncapped 976–1,245) |
| Demo | ~105 s; 6,538 alerts, 99.7% explained; ELEVATED 32–53 s and 72–88 s |
| Slowscan | never ELEVATED; 15 alerts via 10% sample |
| Tests | 23 passing |

---

## 18. Conclusion

> **Say:** "FlowLens shows that explaining every network alert in real time is practical. Tree models with TreeSHAP make each explanation about 800 to 1,100 times faster than the common Kernel SHAP approach, and the two-tier design keeps the system efficient by doing heavy work only when traffic is abnormal. It detects known attacks with a macro F1 of 0.987 and 0.18% false alarms, catches about half of an unseen DoS attack through the Isolation Forest, and processes over a thousand flows per second well within its one-second budget. Its main weaknesses — slow attacks that never raise traffic volume, and unseen attacks that look normal, like Bot — are measured, explained, and clear directions for future work. Thank you."
