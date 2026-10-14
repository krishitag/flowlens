## Dataset and Preprocessing

We use the MachineLearningCSV release of CIC-IDS2017 [1]: eight CSV files, one per capture session, with 2,830,743 labelled flows. Each flow has 78 flow features computed by CICFlowMeter and a `Label` column. Preprocessing (`ml/prepare.py`) runs in these steps:

1. **Cleaning.** Strip whitespace from column names and drop the duplicated `Fwd Header Length` column. Replace ±∞ with missing values and drop those rows (2,867 flows, all with undefined `Flow Bytes/s` and `Flow Packets/s` rates). Then drop exact duplicate rows: 329,896 flows (11.7%) are exact copies of another flow. Deduplicating *before* splitting matters: otherwise identical flows land in both the training and test sets and inflate accuracy.
2. **Label grouping.** Attack labels are grouped into six classes plus BENIGN: **DoS** (Hulk, GoldenEye, slowloris, Slowhttptest), **DDoS**, **PortScan**, **BruteForce** (FTP-Patator, SSH-Patator), **WebAttack** (Brute Force, XSS and SQL Injection) and **Bot**. Infiltration (36 flows) and Heartbleed (11 flows) are dropped because they are too small to train or evaluate on.
3. **Leakage control.** `Destination Port` is kept as `dst_port` for display on the dashboard but is **never** a model feature. The release has no IP addresses, flow identifiers or timestamps, and the script drops them if a variant of the files includes them. These fields identify the testbed's attack hosts rather than describe attack behaviour, and would inflate accuracy. This leaves 76 numeric features.
4. **Sampling.** Each attack class is capped at 50,000 flows and BENIGN at 300,000, which limits training time and softens the class imbalance (after cleaning, BENIGN outnumbers Bot by more than 1,000 to 1).
5. **Splitting.** A stratified 70/15/15 split into training, validation and test sets (random seed 42). The validation set is used to compare the full and reduced feature sets and to set the Isolation Forest threshold; the test set is used only for the final results, and is also what the pipeline replays as live traffic.

After cleaning, 2,497,933 flows remain. After sampling, 463,241 flows are split as below.

**Flows per class** after cleaning, and in each split after sampling.

| Class | After cleaning | Train | Validation | Test |
|---|---:|---:|---:|---:|
| BENIGN | 2,072,254 | 209,999 | 45,000 | 45,001 |
| DoS | 193,730 | 35,000 | 7,500 | 7,500 |
| DDoS | 128,014 | 35,000 | 7,500 | 7,500 |
| PortScan | 90,694 | 35,000 | 7,500 | 7,500 |
| BruteForce | 9,150 | 6,405 | 1,372 | 1,373 |
| WebAttack | 2,143 | 1,500 | 322 | 321 |
| Bot | 1,948 | 1,364 | 292 | 292 |
| **Total** | **2,497,933** | **324,268** | **69,486** | **69,487** |

WebAttack and Bot remain small even after capping the large classes: the test set holds only 321 and 292 of their flows, so their per-class scores are the least stable.
