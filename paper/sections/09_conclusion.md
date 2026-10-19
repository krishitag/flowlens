## Conclusion

The claim that SHAP is too slow for live intrusion detection is true of Kernel SHAP but not of SHAP in general. With tree-based detectors, TreeSHAP computes exact explanations in about [tree_p50] ms per flow, [shap_speedup]× faster than Kernel SHAP, and a two-tier design limits full scoring and explanation to the periods when traffic is abnormal. Together with a cap on explanations per window, these keep per-flow explanations within a one-second window even under stress load. FlowLens explains alerts in plain language and shows them on a dashboard that joins traffic visibility and security alerting in one view. Its classifier is accurate on known attacks (macro F1 [lgbm_macro_f1]). Its Isolation Forest, intended for unseen attacks, helps against volumetric ones but misses attacks whose flows look normal.

Future work includes capturing live traffic instead of replaying records, adding volume-independent triggers to Tier 1 so that low-and-slow attacks are caught beyond the sampling rate, stronger detectors for unseen attacks, and a user study measuring whether the explanations shorten an analyst's triage.

## References

[1] I. Sharafaldin, A. H. Lashkari and A. A. Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization," in *Proc. 4th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2018.

[2] S. M. Lundberg and S.-I. Lee, "A Unified Approach to Interpreting Model Predictions," in *Advances in Neural Information Processing Systems 30 (NeurIPS)*, 2017.

[3] S. M. Lundberg, G. Erion, H. Chen, A. DeGrave, J. M. Prutkin, B. Nair, R. Katz, J. Himmelfarb, N. Bansal and S.-I. Lee, "From local explanations to global understanding with explainable AI for trees," *Nature Machine Intelligence*, vol. 2, pp. 56–67, 2020.

[4] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye and T.-Y. Liu, "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," in *Advances in Neural Information Processing Systems 30 (NeurIPS)*, 2017.

[5] F. T. Liu, K. M. Ting and Z.-H. Zhou, "Isolation Forest," in *Proc. 8th IEEE Int. Conf. Data Mining (ICDM)*, 2008.

[6] G. Engelen, V. Rimmer and W. Joosen, "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study," in *Proc. IEEE Security and Privacy Workshops (SPW)*, 2021.

[7] M. T. Ribeiro, S. Singh and C. Guestrin, "'Why Should I Trust You?': Explaining the Predictions of Any Classifier," in *Proc. 22nd ACM SIGKDD Int. Conf. Knowledge Discovery and Data Mining (KDD)*, 2016.

[8] M. Wang, K. Zheng, Y. Yang and X. Wang, "An Explainable Machine Learning Framework for Intrusion Detection Systems," *IEEE Access*, vol. 8, pp. 73127–73141, 2020.

[9] S. Mane and D. Rao, "Explaining Network Intrusion Detection System Using Explainable AI Framework," arXiv:2103.07110, 2021.

[10] R. Sommer and V. Paxson, "Outside the Closed World: On Using Machine Learning for Network Intrusion Detection," in *Proc. IEEE Symposium on Security and Privacy*, 2010.

[11] D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro and K. Rieck, "Dos and Don'ts of Machine Learning in Computer Security," in *Proc. 31st USENIX Security Symposium*, 2022.
