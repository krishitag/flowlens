## Models

<!-- MEMBER 1 (M1.9): drafted from PLAN.md M1.3-M1.5. Replace or correct, especially
     hyperparameters and the final feature count. -->

**LightGBM classifier.** A multiclass LightGBM model (about 200 trees, `class_weight='balanced'`) predicts one of the seven classes. To keep inference fast and explanations readable, we first train on all features, rank them by gain importance, and retrain on the top 20. The reduced model is kept if its macro F1 stays within about one to two points of the full model. Explanations are therefore always phrased in terms of at most 20 features.

**Isolation Forest.** An Isolation Forest with 100 trees is trained on benign training flows only. Its anomaly score is `score_samples`, where lower means more anomalous. The decision threshold is set on the benign validation split to give about 1% false positives. Because it never sees attack labels, it serves as the detector for attack types missing from the classifier's training data.

**Random Forest baseline.** A 100-tree Random Forest on the same features provides a baseline for the classifier's accuracy. It is not used in the streaming pipeline.

**Exported artefacts.** Training writes the models, the ordered feature list, the class-label map, the Isolation Forest threshold, and per-feature benign baselines (101 percentiles plus the 99.9th) to `models/`. The pipeline loads these at start-up. The baselines are what turn SHAP contributions into sentences such as "above 99.9% of normal flows".
