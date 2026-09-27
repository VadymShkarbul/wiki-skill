"""Verdict rules (T3), rename detection (D4), months, quadrants: synthetic data, no network."""

from datetime import date

import numpy as np
import pytest
from wiki_signal import stats
from wiki_signal.analysis import (
    ArticleUse,
    ConceptInfo,
    EditionResult,
    Verdict,
    _decide,
    assign_quadrants,
    sort_results,
)
from wiki_signal.editions import Edition
from wiki_signal.timeseries import Daily, first_full_month, last_full_month, shift_month

PL = Edition("pl", "plwiki", "pl", "Polish")
CONCEPT = ConceptInfo("Q1", "topic")


def result(**fields):
    r = EditionResult(PL, [])
    defaults = {
        "pairs": 12,
        "median_views": 1000.0,
        "growth": -0.3,
        "interval": stats.Interval(-0.4, -0.2),
        "months_agreeing": 11,
        "despiked_growth": -0.29,
        "spike_days": [],
        "data_from": "2020-01",
    }
    for key, value in {**defaults, **fields}.items():
        setattr(r, key, value)
    return r


def test_clear_consistent_decline_is_high_confidence():
    verdict = _decide(result(), 12)
    assert (verdict.direction, verdict.confidence) == ("declining", "high")
    assert verdict.reasons == ["consistent: 11 of 12 months below the same month last year"]


def test_interval_crossing_zero_is_no_clear_change():
    verdict = _decide(result(growth=-0.1, interval=stats.Interval(-0.24, 0.09)), 12)
    assert (verdict.direction, verdict.confidence) == ("no clear change", None)


def test_each_issue_drops_one_level():
    spiky = result(despiked_growth=-0.15)  # 15 points away from -30%
    assert _decide(spiky, 12).confidence == "medium"
    spiky_small_inconsistent = result(despiked_growth=-0.15, median_views=80, months_agreeing=7)
    verdict = _decide(spiky_small_inconsistent, 12)
    assert verdict.confidence == "low"
    assert any(r.startswith("inconsistent: only 7 of 12") for r in verdict.reasons)
    assert "tiny volume: 80 views/month" in verdict.reasons


def test_spike_flip_counts_even_when_small():
    verdict = _decide(
        result(growth=0.05, interval=stats.Interval(0.01, 0.1), despiked_growth=-0.01), 12
    )
    assert any(r.startswith("spike-driven") for r in verdict.reasons)


def test_insufficient_history_and_volume():
    short = _decide(result(pairs=7, data_from="2025-02"), 12)
    assert short.direction == "insufficient data"
    assert "starts 2025-02" in short.reasons[0]
    quiet = _decide(result(median_views=12), 12)
    assert quiet.direction == "insufficient data"


def test_article_without_data_says_so():
    r = result()
    r.articles = [ArticleUse(CONCEPT, PL, "Brand new", proxy=False)]
    verdict = _decide(r, 12)
    assert verdict.reasons == ["Wikimedia has no pageview data for 'Brand new'"]


def test_quiet_start_is_not_a_rename():
    views = np.r_[np.zeros(60), np.ones(300)]  # rows exist from creation, first view later
    quiet = ArticleUse(
        CONCEPT,
        PL,
        "Stub",
        proxy=False,
        created=date(2024, 1, 2),
        daily=Daily(date(2024, 1, 2), views),
    )
    assert quiet.renamed_hint() is None
    assert quiet.first_month() == "2024-02"


def test_renamed_hint_and_first_month():
    daily = Daily(date(2024, 5, 20), np.ones(400))
    renamed = ArticleUse(
        CONCEPT, PL, "New title", proxy=False, created=date(2006, 6, 1), daily=daily
    )
    assert renamed.renamed_hint() == date(2024, 5, 20)
    assert renamed.first_month() == "2024-06"  # the partial first month is dropped
    fresh = ArticleUse(CONCEPT, PL, "New", proxy=False, created=date(2024, 5, 19), daily=daily)
    assert fresh.renamed_hint() is None
    old = ArticleUse(
        CONCEPT,
        PL,
        "Old",
        proxy=False,
        created=date(2004, 1, 1),
        daily=Daily(date(2015, 7, 1), np.ones(10)),
    )
    assert old.renamed_hint() is None  # data simply starts in 2015-07


@pytest.mark.parametrize(
    ("through", "expected"),
    [(date(2026, 9, 26), "2026-08"), (date(2026, 8, 31), "2026-08"), (date(2026, 3, 1), "2026-02")],
)
def test_last_full_month(through, expected):
    assert last_full_month(through) == expected


def test_month_helpers():
    assert shift_month("2026-01", -12) == "2025-01"
    assert shift_month("2025-12", 1) == "2026-01"
    assert first_full_month(date(2020, 10, 28)) == "2020-11"
    assert first_full_month(date(2020, 10, 1)) == "2020-10"


def test_quadrants_relative_to_median_and_sorting():
    big = result(median_views=5000.0, growth=0.2, interval=stats.Interval(0.1, 0.3))
    small = result(median_views=100.0, growth=0.1, interval=stats.Interval(0.05, 0.2))
    flat = result(median_views=4000.0, growth=0.0, interval=stats.Interval(-0.1, 0.1))
    down = result(median_views=50.0)
    for r, direction in [
        (big, "growing"),
        (small, "growing"),
        (flat, "no clear change"),
        (down, "declining"),
    ]:
        r.verdict = Verdict(direction, None, [])
    assign_quadrants([big, small, flat, down])
    assert [r.quadrant for r in (big, small, flat, down)] == [
        "large & growing",
        "small & growing",
        "large & flat",
        "declining",
    ]
    assert sort_results([small, down, big], "growth") == [big, small, down]
    assert sort_results([small, down, big], "size") == [big, small, down]
