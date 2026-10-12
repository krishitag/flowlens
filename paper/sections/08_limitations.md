## Limitations

**Low-and-slow attacks.** Tier 1 reacts to changes in traffic *volume*. An attack that adds only a few flows per second, such as a slow port scan, never triggers ELEVATED, so its flows are scored only through the 10% sample in the NORMAL state. This is the deliberate cost of tiering, measured in the *Limitations* subsection of the pipeline section with `scenarios/slowscan.json`.

**Dataset artefacts.** CIC-IDS2017 was generated in a testbed, and later analyses report labelling errors and flow-construction artefacts in it [6]. Results on this dataset may overstate how well the same models would perform on a real network. We exclude ports, addresses and timestamps from the features to avoid the most obvious shortcuts, but cannot rule out subtler ones.

**Replayed, not captured, traffic.** The stream is built by resampling labelled flow records. Latency figures therefore exclude packet capture and flow-feature extraction, which a deployment would also need.

**Ground truth on the dashboard.** The dashboard shows each alert's true label so that the demonstration is honest about mistakes. A live deployment has no such label, so analysts would rely on the explanation and the low-confidence tag alone.

**Explanation quality is not user-tested.** We measure how fast explanations are, not how much they help an analyst. Evaluating that would require a user study, which was out of scope.
