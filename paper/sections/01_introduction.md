## Introduction

Operators of a network typically watch two kinds of tools. Traffic dashboards show volumes, rates and top talkers; security tools raise alerts. The two rarely meet. When a machine-learning intrusion detector flags a connection, the analyst sees a class label, perhaps a score, and nothing that explains *why* this flow looked like an attack. Without that reason, the analyst cannot quickly tell a true detection from a false alarm, and cannot trust the detector enough to act on it.

Explainable AI offers a remedy. SHAP [2] attributes a model's output to its input features using Shapley values from cooperative game theory, and several intrusion detection studies attach SHAP explanations to their detections. However, these explanations are usually computed offline, after the fact, and frequently with Kernel SHAP, a model-agnostic estimator that evaluates the model on many perturbed samples per explanation. Kernel SHAP takes seconds per flow, which rules out explaining live traffic flow by flow.

Our claim is that this cost is a consequence of the choice of explainer and architecture, not a property of explanation itself. Two decisions make per-flow explanations practical in real time:

1. **Tree-based detectors explained with TreeSHAP.** TreeSHAP [3] computes *exact* Shapley values for tree ensembles in polynomial time, orders of magnitude faster than Kernel SHAP's sampling.
2. **A two-tier design.** A lightweight monitor watches aggregate traffic. Full scoring and explanation run on every flow only while traffic is abnormal; otherwise only a sample is scored.

We demonstrate this with measurements rather than assertions.

### Contributions

- **FlowLens**, an end-to-end streaming system that replays labelled CIC-IDS2017 flows in real time, detects known attacks with LightGBM and screens for unknown ones with an Isolation Forest trained on benign traffic, explains alerts with TreeSHAP, and presents the result on a live dashboard.
- **A latency study** of detection and explanation per flow, including a direct TreeSHAP versus Kernel SHAP comparison on the same model and flows.
- **A leave-one-attack-out evaluation** that measures how the system behaves on an attack type the classifier never saw during training.
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
