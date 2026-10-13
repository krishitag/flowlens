## Dataset and Preprocessing

<!-- MEMBER 1 (M1.9): this section is drafted from PLAN.md M1.2. Replace it with your own text,
     or correct it and fill in the [placeholders] with the numbers printed by ml/prepare.py. -->

We use the MachineLearningCSV release of CIC-IDS2017 [1], one CSV file per capture day with flow features and a `Label` column. Preprocessing (`ml/prepare.py`) runs in these steps:

1. **Cleaning.** Strip whitespace from column names; drop the duplicated `Fwd Header Length` column; replace ±∞ with missing values and drop those rows; drop exact duplicate rows.
2. **Label grouping.** Attack labels are grouped into six classes plus BENIGN: **DoS** (Hulk, GoldenEye, slowloris, Slowhttptest), **DDoS**, **PortScan**, **BruteForce** (FTP-Patator, SSH-Patator), **WebAttack** (all three web attack labels) and **Bot**. Infiltration and Heartbleed are dropped because they have too few flows to train or evaluate on.
3. **Leakage control.** `Destination Port` is kept as `dst_port` for display on the dashboard, but is **never** a model feature. Neither are IP addresses, flow identifiers or timestamps. These identify the testbed's attack hosts rather than describe attack behaviour, and would inflate accuracy.
4. **Sampling.** Each attack class is capped at 50,000 flows and BENIGN at 300,000, to limit training time and soften class imbalance.
5. **Splitting.** A stratified 70/15/15 split into training, validation and test sets. The test split is what the pipeline replays as live traffic.

After preprocessing, the dataset has [n_total] flows. Per-class counts are in Table [table_class_counts].

[table: class counts per split, from ml/prepare.py output]
