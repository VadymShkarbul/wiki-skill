"""Statistics for growth and trust (decisions M3, T2, T3, T5). Pure numpy, deterministic.

Growth compares each recent month with the same month one year earlier ("month pairs"), which
cancels seasonality. Uncertainty comes from resampling those pairs (bootstrap) with a fixed
seed, so the same data always gives the same numbers.
"""

import math
from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

BOOTSTRAP_SAMPLES = 2000
CI_LEVEL = 0.90
SEED = 0
SPIKE_HALF_WINDOW = 14
SPIKE_MAD_FACTOR = 5.0
SPIKE_MEDIAN_FACTOR = 2.0
SPIKE_MIN_EXCESS = 5.0
MAD_TO_SIGMA = 1.4826


def yoy_growth(current: np.ndarray, previous: np.ndarray) -> float:
    """Growth of the summed current months over the same months a year earlier."""
    base = float(np.sum(previous))
    if base <= 0:
        return math.nan
    return float(np.sum(current)) / base - 1.0


@dataclass(frozen=True)
class Interval:
    low: float
    high: float

    def excludes_zero(self) -> bool:
        return self.low > 0 or self.high < 0


def _resample_indices(n: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    return rng.integers(0, n, size=(BOOTSTRAP_SAMPLES, n))


def _percentiles(samples: np.ndarray) -> Interval:
    samples = samples[np.isfinite(samples)]
    if samples.size == 0:
        return Interval(math.nan, math.nan)
    tail = (1 - CI_LEVEL) / 2 * 100
    low, high = np.percentile(samples, [tail, 100 - tail])
    return Interval(float(low), float(high))


def bootstrap_growth(current: np.ndarray, previous: np.ndarray) -> Interval:
    """90% interval for yoy_growth by resampling month pairs with replacement."""
    idx = _resample_indices(len(current))
    with np.errstate(divide="ignore", invalid="ignore"):
        samples = current[idx].sum(axis=1) / previous[idx].sum(axis=1) - 1.0
    return _percentiles(samples)


def bootstrap_difference(
    current_a: np.ndarray, previous_a: np.ndarray, current_b: np.ndarray, previous_b: np.ndarray
) -> Interval:
    """90% interval for growth(a) - growth(b), resampling the same calendar months for both."""
    idx = _resample_indices(len(current_a))
    with np.errstate(divide="ignore", invalid="ignore"):
        growth_a = current_a[idx].sum(axis=1) / previous_a[idx].sum(axis=1)
        growth_b = current_b[idx].sum(axis=1) / previous_b[idx].sum(axis=1)
    return _percentiles(growth_a - growth_b)


def months_up(current: np.ndarray, previous: np.ndarray) -> int:
    """How many months beat the same month a year earlier."""
    return int(np.sum(current > previous))


def months_down(current: np.ndarray, previous: np.ndarray) -> int:
    return int(np.sum(current < previous))


def theil_sen_annual(values: np.ndarray) -> float:
    """Robust trend of monthly values as %/year, fitted on a log scale (never below -100%).

    Months with zero are skipped, since log(0) is undefined.
    """
    x = np.arange(len(values), dtype=float)
    keep = values > 0
    x, y = x[keep], np.log(values[keep])
    if len(x) < 3:  # noqa: PLR2004 - a slope needs at least three points to be meaningful
        return math.nan
    i, j = np.triu_indices(len(x), k=1)
    slope = float(np.median((y[j] - y[i]) / (x[j] - x[i])))
    return math.exp(12 * slope) - 1.0


@dataclass(frozen=True)
class Spikes:
    cleaned: np.ndarray
    days: np.ndarray  # indices of spike days

    def share_of_views(self, original: np.ndarray) -> float:
        total = float(original.sum())
        return float((original - self.cleaned).sum()) / total if total else 0.0


def despike(daily: np.ndarray) -> Spikes:
    """Replace spike days by their local median (decision T5).

    A day is a spike when it exceeds the median of the surrounding +-14 days by more than
    5 robust standard deviations (MAD-based) and is more than twice that median.
    """
    n = len(daily)
    window = 2 * SPIKE_HALF_WINDOW + 1
    if n < window:
        return Spikes(daily.astype(float), np.array([], dtype=int))
    padded = np.pad(daily.astype(float), SPIKE_HALF_WINDOW, mode="reflect")
    windows = sliding_window_view(padded, window)
    median = np.median(windows, axis=1)
    mad = np.median(np.abs(windows - median[:, None]), axis=1) * MAD_TO_SIGMA
    mad = np.where(mad > 0, mad, 1.0)
    is_spike = (daily > median + SPIKE_MAD_FACTOR * mad) & (
        daily > SPIKE_MEDIAN_FACTOR * median + SPIKE_MIN_EXCESS
    )
    cleaned = np.where(is_spike, median, daily).astype(float)
    return Spikes(cleaned, np.flatnonzero(is_spike))
