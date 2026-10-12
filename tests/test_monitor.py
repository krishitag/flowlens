"""Tests for the tier-1 EWMA monitor state transitions (M2.9)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.monitor import Monitor  # noqa: E402

CALM = 40


def noisy(n):
    """Steady ~40 flows/window with small deterministic noise (38..42)."""
    return [CALM + (i % 5) - 2 for i in range(n)]


def states(monitor, counts):
    return [monitor.update(c)[1] for c in counts]


def warmed_up():
    m = Monitor()
    assert set(states(m, noisy(30))) == {"NORMAL"}
    return m


def test_steady_traffic_stays_normal():
    assert set(states(Monitor(), noisy(200))) == {"NORMAL"}


def test_sustained_spike_flips_after_3_windows():
    m = warmed_up()
    assert states(m, [CALM * 10] * 5) == ["NORMAL", "NORMAL", "ELEVATED", "ELEVATED", "ELEVATED"]


def test_returns_to_normal_only_after_10_calm_windows():
    m = warmed_up()
    states(m, [CALM * 10] * 20)
    assert m.state == "ELEVATED"
    assert states(m, [CALM] * 10) == ["ELEVATED"] * 9 + ["NORMAL"]


def test_calm_streak_resets_on_a_spike():
    m = warmed_up()
    states(m, [CALM * 10] * 5)
    assert states(m, [CALM] * 9 + [CALM * 10] + [CALM] * 9) == ["ELEVATED"] * 19
    assert states(m, [CALM]) == ["NORMAL"]


def test_single_spike_does_not_flip():
    m = warmed_up()
    assert set(states(m, [CALM * 10] + noisy(30))) == {"NORMAL"}


def test_nothing_flips_during_warmup():
    m = Monitor(warmup=10)
    assert states(m, [CALM] + [CALM * 10] * 9) == ["NORMAL"] * 10


def test_baseline_not_learned_while_elevated():
    m = warmed_up()
    mean_before = m.mean
    states(m, [CALM * 10] * 50)
    assert m.mean == mean_before
