"""analyze end to end on recorded live responses (recorded 2026-09-27, data through 2026-09-26).

Expected numbers were cross-checked against an independent prototype over the same window
(see docs/decisions.md, "Trust and confidence").
"""

import json
from datetime import date

import pytest
from wiki_interest.analysis import run_analysis
from wiki_interest.editions import load_catalog
from wiki_interest.errors import SkillError
from wiki_interest.output import save

TODAY = date(2026, 9, 27)
CMD = "uv run /skill/scripts/wiki.py"


@pytest.fixture(scope="module")
def catalog(api):
    return load_catalog(api)


@pytest.fixture(scope="module")
def run(api, catalog):
    cache = {}

    def _run(concepts, editions, **kwargs):
        key = repr((concepts, editions, sorted(kwargs.items())))
        if key not in cache:
            cache[key] = run_analysis(
                api, catalog, concepts, catalog.parse(editions), today=TODAY, **kwargs
            )
        return cache[key]

    return _run


def by_code(analysis):
    return {r.edition.code: r for r in analysis.results}


def test_spec_q1_czech_declines_polish_not_covered(run):
    a = run(["Q1666254"], "pl,cs")
    assert (a.window[0], a.window[-1], a.current[0]) == ("2024-09", "2026-08", "2025-09")
    cs = by_code(a)["cs"]
    assert cs.growth == pytest.approx(-0.477, abs=5e-4)
    assert cs.despiked_growth == pytest.approx(-0.344, abs=5e-4)
    assert (cs.verdict.direction, cs.verdict.confidence) == ("declining", "medium")
    assert cs.months_agreeing == 11
    assert [e.code for e in a.not_covered] == ["pl"]
    assert any("bot detection in 2025" in c for c in a.caveats)
    assert any("2025-03, 2026-04" in c for c in a.caveats)


def test_approved_proxy_fills_the_gap_and_is_labeled(run):
    a = run(["Q1666254"], "pl,cs", proxies=["pl:Post"])
    pl = by_code(a)["pl"]
    assert pl.articles[0].proxy
    assert pl.verdict.direction == "no clear change"
    assert any("uses proxy article 'Post'" in c for c in pl.caveats)
    assert [(d.leader, d.other, d.clear) for d in a.differences] == [("pl", "cs", True)]


def test_spec_q2_astronomy_in_ukrainian(run):
    uk = by_code(run(["Q333"], "uk"))["uk"]
    assert uk.growth == pytest.approx(-0.455, abs=5e-4)
    assert (uk.verdict.direction, uk.verdict.confidence) == ("declining", "high")
    assert uk.seasonal_peak[0] == "09"  # the school year
    assert any("all of uk Wikipedia changed" in c for c in uk.caveats)


def test_spec_q3_english_across_editions(run):
    a = run(["Q1860"], "pl,cs,uk,de,tr")
    assert [r.edition.code for r in a.results] == ["tr", "de", "pl", "cs", "uk"]
    assert {r.edition.code: r.quadrant for r in a.results} == {
        "tr": "large & flat",
        "de": "large & flat",
        "pl": "declining",
        "cs": "declining",
        "uk": "declining",
    }
    assert len(a.differences) == 4


def test_short_window_compares_the_same_months_a_year_earlier(run):
    a = run(["Q1860"], "pl", months=6)
    assert a.current == ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
    assert by_code(a)["pl"].pairs == 6


def test_renamed_article_is_flagged(run):
    a = run(["en:Ecclesiastical Province of the Northern Lights"], "en")
    en = by_code(a)["en"]
    assert en.articles[0].renamed_hint() is not None
    assert en.data_from == "2024-06"
    assert any("probably renamed" in c for c in en.caveats)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"proxies": ["cs:Půst"]}, "does not fill a missing article"),
        ({"proxies": ["Post"]}, "must look like pl:Title"),
        ({"months": 2}, "out of range"),
        ({"proxies": ["de:Fasten"]}, "not in --editions"),
    ],
)
def test_bad_requests(api, catalog, kwargs, message):
    with pytest.raises(SkillError, match=message):
        run_analysis(api, catalog, ["Q1666254"], catalog.parse("pl,cs"), today=TODAY, **kwargs)


def test_free_text_concept_points_to_resolve(api, catalog):
    with pytest.raises(SkillError) as info:
        run_analysis(api, catalog, ["intermittent fasting"], catalog.parse("cs"), today=TODAY)
    assert "Run resolve first" in info.value.next_step


def test_outputs_are_complete_and_relay_ready(run, tmp_path):
    a = run(["Q1666254"], "pl,cs", proxies=["pl:Post"])
    out_dir, summary = save(a, tmp_path, CMD)
    data = json.loads((out_dir / "analysis.json").read_text(encoding="utf-8"))
    json.dumps(data, allow_nan=False)  # no NaN leaks into the file
    assert (out_dir / "trend.png").stat().st_size > 10_000
    assert (out_dir / "growth.png").stat().st_size > 10_000
    assert data["editions"][0]["verdict"]["direction"] in {"declining", "no clear change"}
    assert data["rerun"] == (
        f"{CMD} analyze --concepts Q1666254 --editions pl,cs --months 24 --proxy pl:Post"
    )
    assert "DECLINING -47.7% [90% range" in summary
    assert "Post (proxy)" in summary
    assert f"Re-run: {data['rerun']}" in summary
    assert summary.splitlines()[-1].startswith("Next: tell the user")
