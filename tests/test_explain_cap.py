"""Tests for the per-window explanation cap in pipeline/run.py (pick_to_explain). No models needed."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.run import pick_to_explain  # noqa: E402


def flagged(rows):
    return pd.DataFrame(rows, columns=["source", "pred_prob", "if_score"])


WINDOW = flagged([
    ("iforest", 0.60, -0.70),  # 0: IForest-only, mildly anomalous
    ("lgbm", 0.70, np.nan),    # 1
    ("both", 0.99, -0.80),     # 2: most confident LightGBM flag
    ("iforest", 0.55, -0.90),  # 3: IForest-only, most anomalous
    ("lgbm", 0.95, np.nan),    # 4
])


def picked(cap):
    return set(np.flatnonzero(pick_to_explain(WINDOW, cap)))


def test_under_cap_explains_everything():
    assert picked(300) == {0, 1, 2, 3, 4}


def test_cap_keeps_most_confident_lgbm_first():
    assert picked(1) == {2}
    assert picked(2) == {2, 4}
    assert picked(3) == {1, 2, 4}


def test_iforest_only_after_lgbm_lowest_score_first():
    assert picked(4) == {1, 2, 3, 4}


def test_cap_zero_and_empty_window():
    assert picked(0) == set()
    assert pick_to_explain(WINDOW.iloc[:0], 300).sum() == 0


def test_mask_size_matches_cap():
    mask = pick_to_explain(WINDOW, 2)
    assert mask.dtype == bool and len(mask) == len(WINDOW) and mask.sum() == 2
