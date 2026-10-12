"""Tier-1 monitor (M2.3): EWMA z-score on flows per window -> NORMAL / ELEVATED.

- z compares the current window to the EWMA mean/variance from BEFORE this window.
- NORMAL -> ELEVATED after `on_windows` consecutive windows with z > z_on.
- ELEVATED -> NORMAL after `off_windows` consecutive windows with z < z_off.
- The baseline only learns from calm NORMAL windows (z <= z_on), so an attack
  never becomes the new normal. During the first `warmup` windows it always
  learns and the state stays NORMAL.
"""
import math

MIN_STD = 1.0  # one flow; keeps z finite when early traffic is perfectly steady


class Monitor:
    def __init__(self, alpha=0.1, z_on=3.0, on_windows=3, z_off=2.0, off_windows=5, warmup=10):
        self.alpha = alpha
        self.z_on, self.on_windows = z_on, on_windows
        self.z_off, self.off_windows = z_off, off_windows
        self.warmup = warmup

        self.mean = None
        self.var = 0.0
        self.seen = 0
        self.state = "NORMAL"
        self.high_streak = 0
        self.low_streak = 0

    def update(self, flows_count):
        """Feed one window's flow count; returns (z_score, state)."""
        x = float(flows_count)
        if self.mean is None:
            z = 0.0
        else:
            z = (x - self.mean) / max(math.sqrt(self.var), MIN_STD)
        self.seen += 1

        if self.seen <= self.warmup:
            self._learn(x)
            return z, self.state

        if self.state == "NORMAL":
            self.high_streak = self.high_streak + 1 if z > self.z_on else 0
            if self.high_streak >= self.on_windows:
                self.state, self.high_streak, self.low_streak = "ELEVATED", 0, 0
            elif z <= self.z_on:
                self._learn(x)
        else:
            self.low_streak = self.low_streak + 1 if z < self.z_off else 0
            if self.low_streak >= self.off_windows:
                self.state, self.high_streak, self.low_streak = "NORMAL", 0, 0

        return z, self.state

    def _learn(self, x):
        if self.mean is None:
            self.mean = x
            return
        diff = x - self.mean
        self.mean += self.alpha * diff
        self.var = (1 - self.alpha) * (self.var + self.alpha * diff * diff)
