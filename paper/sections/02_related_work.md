## Related Work

<!-- MEMBER 3: paste the literature review from Review 1 here, then keep the corrected SHAP
     discussion below. Review 1 said "SHAP is too slow, so we avoid it"; that claim is wrong for
     tree models and must not survive into this version. -->

[Review 1 literature review: paste here]

### Shapley-value explanations and their cost

SHAP [2] unifies several local explanation methods under Shapley values: each feature's contribution is its average marginal effect on the model output over all subsets of the other features. Computing this exactly is exponential in the number of features, so practical methods approximate or exploit model structure. **Kernel SHAP** is model-agnostic. It estimates Shapley values with a weighted linear regression over many perturbed samples, replacing "missing" features with values from a background dataset. Every explanation therefore requires many model evaluations, which makes it slow and its cost grows with the background size. **TreeSHAP** [3] instead follows the structure of decision trees and computes *exact* Shapley values for tree ensembles in time polynomial in tree depth and size, with no sampling.

Much of the explainable intrusion detection literature we reviewed uses Kernel SHAP or applies SHAP only offline, to analyse a trained model after evaluation. In the first review we concluded that "SHAP is too slow" for live use. That conclusion holds for Kernel SHAP but not for TreeSHAP. This version tests the distinction directly by timing both explainers on the same model and flows (see Results).

### Detectors

LightGBM [4] is a gradient-boosted decision tree library that grows trees leaf-wise with histogram-based splits. It trains and predicts quickly on tabular data and is directly supported by TreeSHAP. Isolation Forest [5] detects anomalies by randomly partitioning the feature space: anomalous points are isolated in fewer splits, so a short average path length signals an anomaly. Because it is trained only on benign traffic, it can flag attacks that a supervised classifier has never seen. As an ensemble of trees, it is also explainable with TreeSHAP.

### Dataset

CIC-IDS2017 [1] contains five days of benign and attack traffic generated in a controlled testbed, with about 80 bidirectional flow features extracted by CICFlowMeter and a label per flow. Later analyses have identified labelling and flow-construction artefacts in the dataset [6]; we discuss their implications under Limitations.
