"""Tests for the percentile lookup and sentence templates in pipeline/explainer.py (M2.9).

Baselines are hand-made [q0, ..., q100, q99_9] lists, so no models are needed.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.explainer import describe_feature, percentile_of  # noqa: E402


def make_baseline(quantiles, q99_9):
    assert len(quantiles) == 101
    return np.append(np.asarray(quantiles, dtype=float), q99_9)


# q_k = k, so value v sits right at percentile v
LINEAR = make_baseline(np.arange(101), 99.9)
# q0..q60 are 0 (61% of benign flows are 0), then spread up to 1000
TIED_ZEROS = make_baseline(np.concatenate([np.zeros(61), np.linspace(1, 1000, 40)]), 990)
# binary flag: q0..q97 are 0, q98..q100 are 1 (97% of benign flows have no flag)
FLAG = make_baseline([0] * 98 + [1] * 3, 1)


def where(sentence):
    """The part in brackets, e.g. 'above 96% of normal flows'."""
    return sentence[sentence.index("(") + 1 : sentence.rindex(")")]


def test_above_q99_9():
    assert where(describe_feature("F", 99.95, LINEAR)) == "above 99.9% of normal flows"
    assert where(describe_feature("F", 500, LINEAR)) == "above 99.9% of normal flows"


def test_below_q0():
    assert where(describe_feature("F", -1, LINEAR)) == "below every normal flow"


def test_above_x_percent():
    assert where(describe_feature("F", 97, LINEAR)) == "above 96% of normal flows"


def test_below_x_percent():
    assert where(describe_feature("F", 3, LINEAR)) == "below 96% of normal flows"


def test_tied_zeros_not_claimed_above_or_below():
    assert where(describe_feature("F", 0, TIED_ZEROS)) == "same value as about 61% of normal flows"


def test_binary_flag():
    assert where(describe_feature("SYN Flag Count", 1, FLAG)) == "above 97% of normal flows"


def test_typical():
    assert where(describe_feature("F", 50.5, LINEAR)) == "typical for normal flows, percentile 50"


def test_sentence_format():
    assert describe_feature("Flow Packets/s", 4812, LINEAR) == "Flow Packets/s = 4,812 (above 99.9% of normal flows)"


@pytest.mark.parametrize("baseline", [LINEAR, TIED_ZEROS, FLAG])
def test_percentile_of_within_0_100(baseline):
    q = baseline[:101]
    values = np.concatenate([q, [-np.inf, -1e9, -1, 0, 0.5, 1e9, np.inf], np.linspace(-10, 1100, 500)])
    for v in values:
        assert 0 <= percentile_of(v, q) <= 100
