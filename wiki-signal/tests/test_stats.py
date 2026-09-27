"""Known inputs -> known outputs for every statistic the verdicts depend on."""

import math

import numpy as np
import pytest
from wiki_signal import stats


def test_yoy_growth_sums_months():
    assert stats.yoy_growth(np.array([110.0, 90.0]), np.array([100.0, 100.0])) == 0.0
    assert stats.yoy_growth(np.array([150.0]), np.array([100.0])) == pytest.approx(0.5)
    assert math.isnan(stats.yoy_growth(np.array([1.0]), np.array([0.0])))


def test_bootstrap_is_deterministic_and_brackets_the_estimate():
    rng = np.random.default_rng(42)
    previous = rng.uniform(80, 120, 12)
    current = previous * 1.3 * rng.uniform(0.9, 1.1, 12)
    first = stats.bootstrap_growth(current, previous)
    assert first == stats.bootstrap_growth(current, previous)
    growth = stats.yoy_growth(current, previous)
    assert first.low < growth < first.high
    assert first.excludes_zero()


def test_steady_series_gives_a_narrow_interval_and_noise_a_wide_one():
    previous = np.full(12, 100.0)
    steady = stats.bootstrap_growth(previous * 1.2, previous)
    assert steady.high - steady.low < 1e-9
    noisy_current = np.array([60, 150, 80, 140, 70, 160, 90, 130, 75, 145, 85, 115.0])
    noisy = stats.bootstrap_growth(noisy_current, previous)
    assert not noisy.excludes_zero()


def test_difference_interval_shares_month_indices():
    previous = np.full(12, 100.0)
    same = stats.bootstrap_difference(previous * 1.1, previous, previous * 1.1, previous)
    assert same == stats.Interval(0.0, 0.0)
    apart = stats.bootstrap_difference(previous * 1.5, previous, previous * 0.8, previous)
    assert apart.low == pytest.approx(0.7)


def test_months_up_and_down():
    current, previous = np.array([2, 1, 3.0]), np.array([1, 1, 1.0])
    assert stats.months_up(current, previous) == 2
    assert stats.months_down(current, previous) == 0


def test_theil_sen_on_log_scale_is_bounded():
    doubling = 100 * 2 ** (np.arange(24) / 12)  # exactly +100% per year
    assert stats.theil_sen_annual(doubling) == pytest.approx(1.0)
    collapse = 100 * 0.01 ** (np.arange(24) / 12)  # -99% per year, never below -100%
    assert stats.theil_sen_annual(collapse) == pytest.approx(-0.99)
    assert math.isnan(stats.theil_sen_annual(np.array([0, 0, 5.0])))


def test_theil_sen_ignores_one_outlier():
    flat = np.full(24, 100.0)
    flat[10] = 10_000
    assert stats.theil_sen_annual(flat) == pytest.approx(0.0)


def test_despike_finds_isolated_spikes_only():
    rng = np.random.default_rng(1)
    daily = rng.poisson(50, 120).astype(float)
    daily[40] = 900
    daily[80] = 400
    result = stats.despike(daily)
    assert list(result.days) == [40, 80]
    assert result.cleaned[40] < 100
    removed = (daily - result.cleaned).sum() / daily.sum()
    assert 0 < removed < 0.25


def test_despike_leaves_a_level_shift_alone():
    daily = np.r_[np.full(60, 50.0), np.full(60, 200.0)]  # a lasting rise is not a spike
    assert len(stats.despike(daily).days) == 0


def test_despike_needs_small_counts_to_clear_a_floor():
    daily = np.zeros(60)
    daily[30] = 4  # 4 views on a quiet page: below the +5 excess floor
    assert len(stats.despike(daily).days) == 0
