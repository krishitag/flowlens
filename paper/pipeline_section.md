# Streaming Pipeline and Explanation Generation

## System Architecture

The system processes network flows as a stream of fixed-length time windows and runs in five stages: a replayer, a Tier-1 traffic monitor, a Tier-2 detector, an explainer and an event store. The replayer reads a scenario file that describes a sequence of traffic segments, each with a ground-truth label, a flow rate and a duration. Flows are sampled with replacement from the held-out CIC-IDS2017 test split. For each one-second window, the number of flows is drawn from a Poisson distribution with mean equal to the segment rate. Attack segments can mix in a fraction of benign flows (`benign_mix`), so that attacks appear inside background traffic rather than replacing it. The replayer can run in real time, at a multiple of real time, or with no delay for benchmarking.

Each window passes through the Tier-1 monitor, which decides whether traffic is NORMAL or ELEVATED. The Tier-2 detector then scores some or all of the window's flows, depending on that state. Flagged flows are passed to the explainer, which attaches the three features that contributed most to the detection, each with a plain-language sentence. Window statistics and alerts are written to a SQLite database in write-ahead-logging (WAL) mode. This lets the dashboard read the database while the pipeline writes to it. The database has three tables: one row per window (`traffic_windows`), one row per flagged flow (`alerts`), and a key-value table of run summary statistics (`run_meta`).

## Two-Tier Design

### Tier 1: EWMA traffic monitor

The monitor tracks the number of flows per window with an exponentially weighted moving average (EWMA) of the mean and variance, using a smoothing factor α = 0.1. For a window with flow count *x*, the z-score is computed against the mean μ and standard deviation σ from *before* the window is added:

z = (x − μ) / max(σ, 1)

The floor of one flow on σ keeps the z-score finite when early traffic is nearly constant. Tier 1 monitors flow rate only; packet and byte rates are recorded per window but not used for state changes. The first ten windows are a warm-up period: the state stays NORMAL and every window updates the baseline.

After warm-up, the monitor enters ELEVATED when z > 3 for three consecutive windows. It returns to NORMAL when z < 2 for five consecutive windows. The baseline is updated only from NORMAL windows whose z-score is at most 3. It is never updated while the state is ELEVATED, or during the high-z windows just before a transition. Without this rule, attack traffic would become the new baseline, and the first spike window would inflate the variance enough to keep later spike windows below the threshold.

### Choice of exit rule

The project plan initially specified an exit rule of z < 1 for ten consecutive windows. Once the replayer produced Poisson-distributed flow counts, this rule often kept the system ELEVATED long after an attack had ended: ordinary sampling noise produced a window with z ≥ 1 every few windows and reset the count. We compared four settings by simulating the demonstration scenario 200 times with different random seeds. The scenario has 30 s of benign traffic at 40 flows/s, 20 s of DoS at 400 flows/s, 20 s of benign, 15 s of PortScan at 200 flows/s, and 20 s of benign. We measured three outcomes: whether the monitor entered ELEVATED during the first benign segment (a false alarm), whether it returned to NORMAL before the PortScan segment began, and whether it returned to NORMAL before the end of the run.

| Exit rule | False ELEVATED in first benign segment | NORMAL before PortScan | NORMAL before end |
|---|---|---|---|
| z < 1 for 10 windows | 0% | 44% | 38% |
| z < 2 for 10 windows | 0% | 87% | 89% |
| **z < 2 for 5 windows** | **0%** | **100%** | **100%** |
| z < 2.5 for 5 windows | 0% | 100% | 100% |

In all four settings, the monitor entered ELEVATED by the third window of both attack segments in every run. We chose z < 2 for five windows. It recovered in every run, and the looser z < 2.5 setting gave no further improvement.

### Tier 2: detection

In the NORMAL state, the detector scores a random 10% of each window's flows with the LightGBM classifier only. In the ELEVATED state, it scores every flow with both LightGBM and the Isolation Forest. A flow is flagged if LightGBM predicts a non-BENIGN class with probability at least 0.5, or if its Isolation Forest score (`score_samples`) is below a threshold chosen to give about 1% false positives on benign validation flows. Each alert records which model flagged it: `lgbm`, `iforest` or `both`. The predicted class is always LightGBM's, even when only the Isolation Forest flagged the flow; in that case it is usually BENIGN, which tells the analyst the flow is anomalous but not similar to any known attack. Detection latency per flow is the time taken by the model calls for the batch, divided by the number of flows scored.

## Explanation Generation

### TreeSHAP

Explanations use `shap.TreeExplainer`, which computes exact Shapley values for tree ensembles in polynomial time. One explainer is built for LightGBM and one for the Isolation Forest, once, when the pipeline starts. Flagged flows are then explained in a single batch per window. For flows flagged by LightGBM, or by both models, the explainer uses the SHAP values for the predicted class, in log-odds units. A positive value means the feature pushed the flow toward that attack class. If only the Isolation Forest flagged a flow, or LightGBM predicted BENIGN, the Isolation Forest explainer is used instead, because benign-class contributions would explain the wrong outcome.

### Isolation Forest sign handling

TreeSHAP explains an Isolation Forest in terms of path length. A short path means a point is easy to isolate, and therefore anomalous. A negative SHAP value thus pushes a flow toward "anomalous". The explainer negates these values, so that for both models a positive contribution means "pushes toward anomalous", and the dashboard can show them on the same scale. To check this sign convention, we sample 500 test flows, sum each flow's raw Isolation Forest SHAP values, and correlate the sums with the model's `score_samples` output, where higher means more normal. A correct sign gives a strong positive correlation. On the final models, the correlation was [iforest_sign_corr].

### From contributions to sentences

For each flagged flow, the explainer keeps the three features with the largest positive contributions. Each feature value is compared against the benign distribution of that feature in the training set. This distribution is stored as 101 percentiles (0th to 100th) plus the 99.9th percentile. The value's position is found by binary search (`np.searchsorted`) and turned into a sentence, for example `Flow Packets/s = 4,812 (above 99.9% of normal flows)`.

Many CIC-IDS2017 features are zero for most benign flows, such as flag counts and some inter-arrival times, so many of the stored percentiles are equal. A single lookup would then make misleading claims; for example, a value of 0 could be described as "above 60% of normal flows" when it is simply equal to them. The explainer therefore searches twice. The leftmost insertion point gives the share of benign percentiles strictly below the value, which is used only for "above X%" claims. The rightmost insertion point gives the share strictly above it, which is used only for "below X%" claims. The rules are checked in this order:

1. Above the 99.9th percentile: "above 99.9% of normal flows".
2. Below the minimum: "below every normal flow".
3. At least 90% strictly below: "above X% of normal flows".
4. At least 90% strictly above: "below X% of normal flows".
5. Equal to at least 20 percentiles: "same value as about X% of normal flows".
6. Otherwise: "typical for normal flows, percentile X".

Unit tests cover each rule with hand-made baselines, including a feature where 61% of benign values are zero and a binary flag that is zero for 97% of benign flows.

Each alert stores the three features as JSON, each with its name, value, contribution and percentile, together with the sentences. The dashboard uses these to draw a contribution bar chart for the selected alert.

## Latency Evaluation

Latency is measured with a stress scenario of five 20-second segments: benign traffic at 200 flows/s, DoS at 2,000 flows/s with 30% benign flows mixed in, DDoS at 2,000 flows/s, PortScan at 1,000 flows/s, and benign traffic at 200 flows/s. The scenario is replayed with no delay into a temporary database, and four quantities are recorded:

- **Detection latency per scored flow:** each window's model time divided by the number of flows scored in it, counted once for every scored flow, not only for flagged ones.
- **Explanation latency per explained flow:** each window's explanation time, including the sentence formatting, divided by the number of flows explained.
- **End-to-end latency per window:** the time from receiving a window to finishing the database writes for it.
- **Work per state:** the share of flows scored and explained in NORMAL and in ELEVATED windows.

On the final models, detection latency was [p50_detect_ms] ms at the median and [p95_detect_ms] ms at the 95th percentile. Explanation latency was [p50_explain_ms] ms and [p95_explain_ms] ms. End-to-end latency per window was [p50_e2e_ms] ms and [p95_e2e_ms] ms, compared with the window length of 1,000 ms. In NORMAL windows, [pct_scored_normal]% of flows were scored and [pct_explained_normal]% explained. In ELEVATED windows the figures were [pct_scored_elevated]% and [pct_explained_elevated]%.

## Limitations

**Low-and-slow attacks.** Tier 1 reacts only to changes in total traffic volume. A scan that adds a few flows per second to normal traffic does not change the window counts enough to trigger ELEVATED. In the slow-scan scenario, 30 seconds of PortScan at about 5 flows/s were mixed into roughly 40 benign flows/s. The system stayed NORMAL for the entire run, and the highest z-score during the scan was 3.41, in a single window. Only the 10% sample was scored, and 15 of the 153 scan flows raised alerts. Such attacks are therefore detected only at the sampling rate. This is the cost of avoiding full scoring and explanation during normal operation.

**Frozen baseline.** Because the baseline is not updated while ELEVATED, the monitor assumes that every period of high traffic eventually ends. A legitimate, lasting increase in traffic, such as a new service or a busy period, would keep the system ELEVATED indefinitely. Every flow would then be scored and explained, removing the savings from tiering, until an operator reset the baseline.

**Volume-only monitoring.** The monitor uses flow counts only. Attacks that change what the traffic looks like without changing how much there is are left entirely to the 10% sample in NORMAL state.
