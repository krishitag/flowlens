## Related Work

<!-- MEMBER 3: written from well-known references because the Review 1 literature review
     wasn't available here. Add or swap in the Review 1 papers if the reviewers expect them,
     and keep the corrected SHAP discussion: Review 1's "SHAP is too slow" claim must not return. -->

### Interpretability in network intrusion detection

Machine learning has long promised to detect attacks that traditional rules miss, but it has been sparsely used in operational networks. Sommer and Paxson [10] attribute this partly to a semantic gap: an operator cannot act on an alert without understanding why the model raised it. Arp et al. [11] identify spurious correlations, where a model learns artefacts of the dataset rather than the attack, as a common pitfall of machine learning in security, and recommend explanation methods to detect them. Explanations therefore serve two readers: the analyst triaging an alert, and the researcher checking that the model learned something real.

Local explanation methods attribute a single prediction to its input features. LIME [7] fits a simple surrogate model around the instance being explained; SHAP [2] attributes the prediction with Shapley values from cooperative game theory. Both have been applied to intrusion detection. Wang et al. [8] use SHAP to explain an anomaly detection system’s decision both locally, per connection, and globally, per attack type. Mane and Rao [9] compare various explanation methods, including SHAP and LIME, on a neural-network intrusion detector. Both studies compute explanations offline on a standard dataset; neither measure what explanation costs at streaming rates, which is the main concern this framework addresses.

### Shapley-value explanations and their cost

SHAP [2] unifies several local explanation methods under Shapley values: each feature's contribution is its average marginal effect on the model output over all subsets of the other features. Computing this exactly is exponential in the number of features, so practical methods approximate or exploit model structure. **Kernel SHAP** is model-agnostic and estimates Shapley values with a weighted linear regression over many perturbed samples, replacing "missing" features with values from a background dataset. Every explanation therefore requires many model evaluations, which makes it slow and its cost grows with the background size. **TreeSHAP** [3] instead follows the structure of decision trees and computes *exact* Shapley values for tree ensembles in time polynomial in tree depth and size, with no sampling.

In the first review we concluded that "SHAP is too slow" for live use. That conclusion holds for Kernel SHAP but not for TreeSHAP. This version tests the distinction directly by timing both explainers on the same model and flows (see Results).

### Detectors

LightGBM [4] is a gradient-boosted decision tree library that grows trees leaf-wise with histogram-based splits. It trains and predicts quickly on tabular data and is directly supported by TreeSHAP. Isolation Forest [5] detects anomalies by randomly partitioning the feature space: anomalous points are isolated in fewer splits, so a short average path length signals an anomaly. Because it is trained only on benign traffic, it can flag attacks that a supervised classifier has never seen. As an ensemble of trees, it is also explainable with TreeSHAP.

### Dataset

CIC-IDS2017 [1] contains five days of benign and attack traffic generated in a controlled testbed, with about 80 bidirectional flow features extracted by CICFlowMeter and a label per flow. Later analyses have identified labelling and flow-construction artefacts in the dataset [6]; their implications are discussed under Limitations.
