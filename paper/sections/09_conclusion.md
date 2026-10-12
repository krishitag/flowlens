## Conclusion

The claim that SHAP is too slow for live intrusion detection is true of Kernel SHAP but not of SHAP in general. With tree-based detectors, TreeSHAP computes exact explanations in about [tree_p50] ms per flow, and a two-tier design limits full scoring and explanation to the periods when traffic is abnormal. Together these make per-flow explanations practical on a live stream. FlowLens combines a supervised classifier for known attacks with an Isolation Forest for unseen ones, explains every alert in plain language, and shows the result on a dashboard that joins traffic visibility and security alerting in one view.

Future work includes capturing live traffic instead of replaying records, adding volume-independent triggers to Tier 1 so that low-and-slow attacks are caught beyond the sampling rate, and a user study measuring whether the explanations shorten an analyst's triage.

## References

[1] I. Sharafaldin, A. H. Lashkari and A. A. Ghorbani, "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization," in *Proc. 4th Int. Conf. Information Systems Security and Privacy (ICISSP)*, 2018.

[2] S. M. Lundberg and S.-I. Lee, "A Unified Approach to Interpreting Model Predictions," in *Advances in Neural Information Processing Systems 30 (NeurIPS)*, 2017.

[3] S. M. Lundberg, G. Erion, H. Chen, A. DeGrave, J. M. Prutkin, B. Nair, R. Katz, J. Himmelfarb, N. Bansal and S.-I. Lee, "From local explanations to global understanding with explainable AI for trees," *Nature Machine Intelligence*, vol. 2, pp. 56–67, 2020.

[4] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Ye and T.-Y. Liu, "LightGBM: A Highly Efficient Gradient Boosting Decision Tree," in *Advances in Neural Information Processing Systems 30 (NeurIPS)*, 2017.

[5] F. T. Liu, K. M. Ting and Z.-H. Zhou, "Isolation Forest," in *Proc. 8th IEEE Int. Conf. Data Mining (ICDM)*, 2008.

[6] G. Engelen, V. Rimmer and W. Joosen, "Troubleshooting an Intrusion Detection Dataset: the CICIDS2017 Case Study," in *Proc. IEEE Security and Privacy Workshops (SPW)*, 2021.

<!-- MEMBER 3: add the Review 1 references here when pasting the literature review. -->
