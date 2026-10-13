## Analyst Dashboard

The dashboard is a Streamlit application that reads the event database once per second, read-only, while the pipeline writes to it. Because the database runs in WAL mode, these reads never block the writer. The dashboard is designed around the question an analyst asks on seeing an alert: *what is happening, what was flagged, and why?*

**Traffic state at a glance.** A row of indicators shows the current Tier-1 state (green for NORMAL, red for ELEVATED) and its z-score, the flow rate against the recent normal baseline, packets per second, alerts in the last 60 seconds, and the share of the latest window's flows that Tier 2 scored. A status indicator distinguishes a live run, a paused view and a completed run.

**Traffic over time.** Flow rate and the monitor's z-score are drawn as two panels on a shared time axis. The z-score panel marks the entry (z > 3) and exit (z < 2) thresholds, and ELEVATED periods are shaded across both panels. The viewer can therefore see not only *that* the state changed but *why*: three consecutive windows above the entry line. We use two aligned panels rather than a dual-axis chart, because two different y-scales on one plot invite false visual correlations.

**Alerts.** A table lists the 50 most recent alerts: time, destination port, predicted class and confidence, which model raised the alert (LightGBM, Isolation Forest or both), the ground-truth label and whether the prediction matched it. The ground truth is shown for honesty during the demonstration; a deployed system would not have it. A second panel counts alerts per predicted class and per detecting model.

**Explanations.** Selecting an alert shows its top features as a horizontal bar chart of SHAP contributions toward "anomalous", next to the explanation sentences, which compare each feature's value with the benign distribution. Contributions from LightGBM and the Isolation Forest share one sign convention (positive means "pushes toward anomalous"), so both can be plotted on the same axis. An alert is tagged **low confidence** when both models scored the flow but only one flagged it. The analyst can pin an alert by ID while new alerts continue to arrive, and can pause live updates to discuss a single alert.

**Operational statistics and results.** A sidebar reports the median and 95th-percentile detection and explanation latency, computed live from the alerts table, and the share of flows scored and explained in each state, from the window table. A separate tab presents the offline results (classification metrics, the leave-one-attack-out study, the TreeSHAP versus Kernel SHAP benchmark and the pipeline latency report), read directly from the JSON reports the other components produce.

The visual design uses a dark, neutral palette. Colour is reserved for state (NORMAL, ELEVATED, low confidence) and always paired with a text label, so it never carries meaning on its own.
