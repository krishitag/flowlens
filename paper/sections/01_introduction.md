## Introduction

Network operators typically oversee two kinds of tools: traffic dashboards that show volumes, rates, top talkers and security tools that raise alerts. There is no concept of integration where both tools could be combined to provide explainability beyond certain patterns and flows. When a machine-learning intrusion detector flags a connection, the analyst only sees a class label and a value. However, nothing explains why this flow was flagged for abnormality and for that reason, the analyst cannot quickly tell an actual anomaly from a false alarm, and the detector cannot be trusted to enable direct action.

Explainable AI provides connectivity and reasoning where SHAP [2] attributes a model’s output to its input features using Shapley values from cooperative game theory, and several intrusion detection studies attach SHAP explanations to their detections. However, these explanations are computed offline, after the fact, and frequently with Kernel SHAP, a model-agnostic estimator that evaluates the model on multiple jittered samples per explanation. Kernel SHAP takes seconds per flow, rather than flow-by-flow, resulting in its inability to explain flows instantaneously.

Our claim is that this cost is a consequence of architectural choice and can be minimized by combining two decisions to improve the practicality of real-time per-flow explanations:

1. **Tree-based detectors explained with TreeSHAP.** TreeSHAP [3] computes *exact* Shapley values for tree ensembles in polynomial time, orders of magnitude faster than Kernel SHAP's sampling.
2.	**A two-tier structure.** A lightweight monitor watches aggregate traffic while a tier that deals with full scoring and explanation runs on every flow only while traffic is abnormal; otherwise only a sample is scored.

This is demonstrated with measurements rather than assertions.

### Contributions

- **FlowLens**, an end-to-end streaming system that replays labelled CIC-IDS2017 flows in real time, detects known attacks with LightGBM and screens for unknown ones with an Isolation Forest trained on benign traffic, explains alerts with TreeSHAP, and presents the result on a live dashboard.
- **A latency study** of detection and explanation per flow, including a direct TreeSHAP versus Kernel SHAP comparison on the same model and flows.
- **A leave-one-attack-out evaluation** that measures how the system behaves on an unseen attack type that wasn’t a part of the training set.
- **A measurement of the compute saved by tiering**, as the share of flows scored and explained in NORMAL versus ELEVATED states.

### Changes since the first review

| First review | Now | Reason |
|---|---|---|
| "SHAP is too slow, so we avoid it" | TreeSHAP on tree models, benchmarked against Kernel SHAP | TreeSHAP is fast; the slow variant is Kernel SHAP |
| Custom Python traffic simulator | Replay of real labelled CIC-IDS2017 flows as a live stream | Real traffic features and labels, less code, no artificially easy attacks |
| "Predictive" framework | Removed | Nothing in the system predicts future traffic |
| Random Forest *or* Isolation Forest | LightGBM (supervised, attack type) *and* Isolation Forest (unsupervised, unseen attacks); Random Forest as a baseline | The two models do different jobs: known and unseen attacks |
| "Tested on realistic datasets" | CIC-IDS2017 with a leave-one-attack-out test | Named and reproducible; the holdout shows behaviour on unseen attacks |
| Analyst usability metric | Removed | Not measurable within the project's scope |
