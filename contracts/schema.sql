PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS traffic_windows (
  ts        REAL PRIMARY KEY,   -- simulated seconds since run start
  flows     INTEGER,
  packets   INTEGER,
  bytes     INTEGER,
  z_score   REAL,
  state     TEXT,               -- 'NORMAL' | 'ELEVATED'
  scored    INTEGER,            -- flows scored by tier 2 in this window
  explained INTEGER             -- flows explained in this window
);

CREATE TABLE IF NOT EXISTS alerts (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts           REAL,
  flow_idx     INTEGER,         -- row index in test.parquet
  dst_port     INTEGER,
  true_label   TEXT,            -- ground truth, shown for demo honesty
  pred_label   TEXT,
  pred_prob    REAL,
  if_score     REAL,
  source       TEXT,            -- 'lgbm' | 'iforest' | 'both'
  top_features TEXT,            -- JSON: [{"name","value","contribution","percentile"}]
  explanation  TEXT,            -- human sentence(s)
  detect_ms    REAL,
  explain_ms   REAL
);

CREATE TABLE IF NOT EXISTS run_meta (key TEXT PRIMARY KEY, value TEXT);
