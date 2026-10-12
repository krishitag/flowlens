"""SQLite event store (M2.1). Schema comes from contracts/schema.sql (WAL mode),
so the dashboard can read while the pipeline writes.
"""
import json
import sqlite3
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent.parent / "contracts" / "schema.sql"

WINDOW_COLS = ["ts", "flows", "packets", "bytes", "z_score", "state", "scored", "explained"]
ALERT_COLS = [
    "ts", "flow_idx", "dst_port", "true_label", "pred_label", "pred_prob", "if_score",
    "source", "top_features", "explanation", "detect_ms", "explain_ms",
]


def _insert_sql(table, cols):
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"


class Store:
    def __init__(self, db_path="data/events.db"):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA.read_text())

    def insert_window(self, window):
        """One traffic_windows row; `window` needs every key in WINDOW_COLS."""
        self.conn.execute(_insert_sql("traffic_windows", WINDOW_COLS), window)
        self.conn.commit()

    def insert_alerts(self, alerts):
        """All alerts for one window in a single executemany; each needs every key in ALERT_COLS."""
        if not alerts:
            return
        self.conn.executemany(_insert_sql("alerts", ALERT_COLS), alerts)
        self.conn.commit()

    def set_meta(self, key, value):
        """Store a run_meta value; non-strings are saved as JSON."""
        if not isinstance(value, str):
            value = json.dumps(value)
        self.conn.execute("INSERT OR REPLACE INTO run_meta (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def close(self):
        self.conn.close()
