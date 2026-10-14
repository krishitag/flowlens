## Models

All models are trained by one command (`python ml/train.py`, about 30 seconds on a laptop) with fixed random seeds.

**LightGBM classifier.** A multiclass LightGBM model with 200 trees and otherwise default parameters predicts one of the seven classes. Classes are weighted inversely to their frequency (`class_weight='balanced'`), because without weighting the model barely learned the rare classes: validation macro F1 fell to 0.52. To keep inference fast and explanations readable, we first train on all 76 features, rank them by gain importance, and retrain on the top 20. On the validation set the full model reaches a macro F1 of 0.990 and the 20-feature model 0.972, a drop of 1.8 points, which is within the 1–2 points we accepted in exchange for shorter explanations. The 20-feature model is the one used everywhere else. Its features are, in order of importance:

`Init_Win_bytes_backward`, `Flow Duration`, `Bwd Header Length`, `Total Length of Bwd Packets`, `Bwd Packet Length Min`, `Bwd IAT Min`, `Idle Min`, `PSH Flag Count`, `Fwd Header Length`, `min_seg_size_forward`, `Fwd PSH Flags`, `Total Backward Packets`, `Init_Win_bytes_forward`, `Flow IAT Max`, `Idle Mean`, `Total Length of Fwd Packets`, `Bwd Packet Length Std`, `act_data_pkt_fwd`, `Packet Length Std`, `Fwd Packet Length Std`.

Most of the loss falls on WebAttack, where the 20-feature model confuses some benign web flows with attacks. A softer class weighting (the square root of the balanced weights) gave the same result, so we kept the balanced weights.

**Isolation Forest.** An Isolation Forest with 100 trees (256 samples per tree, the default) is trained on the 209,999 benign training flows only, using the same 20 features. Its anomaly score is `score_samples`, where lower means more anomalous. The decision threshold is the 1st percentile of the scores of benign validation flows (−0.665), so about 1% of benign flows are flagged; on the test set the rate is 0.93%. Because it never sees attack labels, it is the detector intended for attack types missing from the classifier's training data.

**Random Forest baseline.** A 100-tree Random Forest on the same 20 features provides a baseline for the classifier's accuracy. It is not used in the streaming pipeline.

**Exported artefacts.** Training writes the models, the ordered feature list, the class-label map, the Isolation Forest threshold, and per-feature benign baselines (101 percentiles plus the 99.9th, from benign training flows) to `models/`. The pipeline loads these at start-up. The baselines are what turn SHAP contributions into sentences such as "above 99.9% of normal flows".
