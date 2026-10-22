# FlowLens: Explainable Real-Time Network Anomaly Detection

**Review 3 · Computer Networks, VIT** · Krishita Gupta, Krish Singh, Vedika

---

## 1. What is FlowLens?

FlowLens watches network traffic, detects attacks, and **explains why** each connection was flagged, while traffic is still arriving. A live dashboard shows the traffic, the alerts and the reasons.

We use the **CIC-IDS2017** dataset (real lab traffic with labelled attacks) and replay it second by second as if it were live.

## 2. The problem

- ML-based intrusion detection usually gives only a label ("DoS") with **no reason**.
- Research that does give reasons uses **Kernel SHAP**, which takes about **2 seconds per connection**. That is far too slow for live traffic with hundreds of connections per second.

## 3. Our idea (novelty)

1. **Use tree models and TreeSHAP.** TreeSHAP gives exact explanations for tree models in **2.4 ms per flow**, about **800–1,100× faster** than Kernel SHAP. That makes live explanations possible.
2. **Two tiers.** Do the heavy work only when traffic looks abnormal, to save compute.
3. **Two models.** A supervised model for known attacks and an unsupervised model for unusual traffic it was never trained on.
4. **Plain-language reasons.** Each alert says which 3 features caused it, compared with normal traffic.

## 4. How it works

```
Replayer ──▶ Tier 1 ──▶ Tier 2 ──▶ Explainer ──▶ Database ──▶ Dashboard
(1-second    (normal or   (ML         (TreeSHAP,     (SQLite)     (Streamlit)
 windows)     abnormal?)   models)     top 3 reasons)
```

**Tier 1: quick check.** Every second it counts the flows and compares the count with a running average (EWMA). If traffic is unusually high for 3 seconds in a row, the state becomes **ELEVATED**. After 5 calm seconds it returns to **NORMAL**.

**Tier 2: detailed check.**
- NORMAL: LightGBM checks a random **10%** of flows.
- ELEVATED: LightGBM **and** Isolation Forest check **every** flow.

**The two models:**

| Model | What it does |
|---|---|
| LightGBM | Learned from labelled data; names the attack type (DoS, DDoS, PortScan, BruteForce, WebAttack, Bot) |
| Isolation Forest | Learned only normal traffic; flags anything unusual, including attacks it never saw |

If the two models disagree, the alert is marked **low confidence**.

**Explanation.** For each alert, TreeSHAP finds the 3 features that pushed the model most toward "attack". Each one is compared with normal traffic. A real example from our demo (a port scan):

```
Flow Duration = 36 (below 92% of normal flows)
PSH Flag Count = 1 (same value as about 27% of normal flows)
Total Length of Fwd Packets = 2 (typical for normal flows, percentile 13)
```

The connection lasted 36 microseconds and sent 2 bytes. A scanner knocks on a port and leaves immediately.

**Features.** The models use 20 flow features, such as duration, bytes each way, gaps between packets and TCP flags. We do **not** use port numbers, IP addresses or timestamps, because they would let the model cheat (data leakage).

## 5. Results (real data)

| Measure | Result |
|---|---|
| Explanation time per flow | **TreeSHAP 2.4 ms vs Kernel SHAP ~2.6 s (~800–1,100× faster)** |
| Accuracy (macro F1) | **0.972** LightGBM (Random Forest baseline 0.986) |
| False alarms on normal traffic | **0.37%** |
| Attack never seen in training (DoS) | **37.8%** still caught |
| Speed under heavy load (~1,100 flows/s) | **223 ms** per 1-second window (p95) |
| Live demo | 6,550 alerts, **99.7% explained** |

We chose LightGBM over Random Forest because it predicts one flow about 40× faster (0.34 ms vs 14 ms), which matters for a live system.

## 6. Advantages

- Every alert comes with a reason a human can read
- Fast enough for live traffic, and we measured it
- Saves compute: only 10% of flows are checked when traffic is normal
- Catches some unseen attacks through the Isolation Forest
- No data leakage; results can be reproduced with one command each

## 7. Limitations

- **Slow attacks:** a slow port scan doesn't raise traffic volume, so Tier 1 never goes ELEVATED and only the 10% sample catches it.
- **Attacks that look normal:** an unseen Bot attack was caught 0% of the time.
- **WebAttack** is the weakest class (F1 0.86): few examples, and it looks like normal browsing.
- **Replayed traffic:** we replay recorded flows rather than capturing live packets.

## 8. Tech stack

Python 3.11 · pandas · LightGBM · scikit-learn · SHAP · SQLite · Streamlit + Plotly · pytest · GitHub

## 9. Project structure

| Folder | Contents |
|---|---|
| `ml/` | Data cleaning, training, evaluation, SHAP benchmark |
| `models/` | Trained models, the 20 features, normal-traffic baselines |
| `pipeline/` | Replayer, Tier 1 monitor, Tier 2 detector, explainer, database |
| `dashboard/` | Live Streamlit dashboard |
| `scenarios/` | Traffic scripts: demo, stress test, slow scan |
| `tests/` | 23 unit tests |
| `reports/` | Results and figures |

## 10. Live demo

Two terminals in the project folder:

```bash
streamlit run dashboard/app.py                                     # dashboard
python -m pipeline.run --scenario scenarios/demo.json --speed 1    # live traffic
```

What you will see (about 105 seconds):
1. **0–30 s:** normal traffic, green NORMAL, only 10% of flows checked.
2. **~30 s:** a **DoS attack**. Traffic jumps, the state turns red ELEVATED, alerts appear. We open one alert and read its explanation.
3. **~53 s:** the attack ends and the state returns to NORMAL.
4. **~70 s:** a **port scan**. ELEVATED again, with different features explaining it.
5. **End:** the sidebar shows latency and how much work tiering saved. The Results tab shows the TreeSHAP vs Kernel SHAP comparison.

## 11. Tests

```bash
pytest tests/ -q       # 23 passed
```

| Test file | Checks |
|---|---|
| `test_monitor.py` (7) | Tier 1 turns ELEVATED after exactly 3 abnormal seconds, returns after 5 calm ones, and ignores a single spike |
| `test_explainer.py` (9) | Explanation sentences ("above 99% of normal flows", etc.) are correct |
| `test_explain_cap.py` (5) | Under heavy load, the most confident alerts are explained first |

## 12. Future work

- Capture live packets instead of replaying recorded flows
- Detect slow scans by tracking ports per source in Tier 1
- Test on newer datasets (CIC-IDS2018, UNSW-NB15)
