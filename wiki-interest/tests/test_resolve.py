"""Resolve behavior on recorded live responses (recorded 2026-09-27)."""

import pytest
from wiki_interest.editions import load_catalog
from wiki_interest.errors import SkillError
from wiki_interest.resolve import (
    TitleRef,
    find_candidates,
    format_candidates,
    make_concept,
    parse_ref,
)

CMD = "uv run /skill/scripts/wiki.py"


@pytest.fixture(scope="module")
def catalog(api):
    return load_catalog(api)


def eds(catalog, text):
    return catalog.parse(text)


# --- editions ---------------------------------------------------------------------------


def test_editions_accept_codes_dbnames_and_english_names(catalog):
    parsed = catalog.parse("pl, cswiki,Ukrainian,pl")
    assert [e.code for e in parsed] == ["pl", "cs", "uk"]
    assert parsed[2].label() == "uk (Ukrainian)"


def test_edition_code_differs_from_language_code(catalog):
    yue = catalog.parse("zh-yue")[0]
    assert (yue.code, yue.lang, yue.dbname, yue.project) == (
        "zh-yue",
        "yue",
        "zh_yuewiki",
        "zh-yue.wikipedia",
    )


def test_country_code_gets_a_hint(catalog):
    with pytest.raises(SkillError) as info:
        catalog.parse("cz")
    assert "Did you mean cs (Czech)?" in info.value.next_step


def test_real_edition_code_is_not_rewritten(catalog):
    assert catalog.parse("se")[0].label() == "se (Northern Sami)"


def test_typo_gets_close_matches(catalog):
    with pytest.raises(SkillError) as info:
        catalog.parse("polsih")
    assert "pl (Polish)" in info.value.next_step


def test_too_many_editions(catalog):
    codes = ",".join(list(catalog.by_code)[:16])
    with pytest.raises(SkillError, match="limit is 15"):
        catalog.parse(codes)


# --- references -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Q333", "Q333"),
        ("q1666254", "Q1666254"),
        ("pl:Astronomia", ("pl", "Astronomia")),
        ("https://pl.m.wikipedia.org/wiki/Przerywany_post#Historia", ("pl", "Przerywany post")),
        (
            "https://cs.wikipedia.org/wiki/P%C5%99eru%C5%A1ovan%C3%BD_p%C5%AFst",
            ("cs", "Přerušovaný půst"),
        ),
        (
            "https://uk.wikipedia.org/w/index.php?title=Астрономія&action=history",
            ("uk", "Астрономія"),
        ),
        ("Star Wars: Episode IV", None),
        ("astronomy", None),
    ],
)
def test_parse_ref(catalog, text, expected):
    ref = parse_ref(text, catalog)
    if isinstance(ref, TitleRef):
        ref = (ref.edition.code, ref.title)
    assert ref == expected


def test_url_of_unknown_edition_is_an_error(catalog):
    with pytest.raises(SkillError):
        parse_ref("https://xx-nope.wikipedia.org/wiki/X", catalog)


# --- candidates -------------------------------------------------------------------------


def test_spec_q1_polish_not_covered_with_broader_proxies(api, catalog):
    editions = eds(catalog, "pl,cs")
    concepts = find_candidates(api, catalog, "intermittent fasting", editions)
    first = concepts[0]
    assert first.qid == "Q1666254"
    assert first.titles == {"cs": "Přerušovaný půst"}
    assert [p.title for p in first.proxies["pl"]] == ["Post", "Dieta"]
    assert first.proxies["pl"][0].via == "broader concept: fasting, Q44602"


def test_ambiguous_topic_lists_notable_meanings_first(api, catalog):
    concepts = find_candidates(api, catalog, "Mercury", eds(catalog, "en,pl"))
    assert [c.qid for c in concepts] == ["Q308", "Q925", "Q1150"]  # planet, element, god


def test_exact_matches_rank_above_popular_prefix_matches(api, catalog):
    concepts = find_candidates(api, catalog, "Go", eds(catalog, "en"))
    qids = [c.qid for c in concepts]
    assert "Q11413" in qids  # the board game
    assert "Q37227" in qids  # the programming language
    assert "Q95" not in qids  # Google matches only by prefix


def test_topic_in_ukrainian(api, catalog):
    concepts = find_candidates(
        api, catalog, "інтервальне голодування", eds(catalog, "uk"), search_lang="uk"
    )
    assert concepts[0].qid == "Q1666254"


def test_title_ref_follows_typo_and_redirect(api, catalog):
    concepts = find_candidates(api, catalog, "en:intermittant fasting", eds(catalog, "cs"))
    assert [c.qid for c in concepts] == ["Q1666254"]


def test_missing_article_title(api, catalog):
    with pytest.raises(SkillError, match="No article 'Zzqxv nope'"):
        find_candidates(api, catalog, "pl:Zzqxv nope", eds(catalog, "pl"))


def test_nonexistent_qid(api, catalog):
    with pytest.raises(SkillError, match="Q999999999 is not a topic"):
        find_candidates(api, catalog, "Q999999999", eds(catalog, "pl"))


def test_no_match(api, catalog):
    with pytest.raises(SkillError) as info:
        find_candidates(api, catalog, "zzqxv nonsense topic", eds(catalog, "pl"))
    assert "--search-lang" in info.value.next_step


# --- filtering and output ---------------------------------------------------------------


def test_items_without_articles_and_wikimedia_pages_are_dropped(catalog):
    editions = eds(catalog, "en")
    no_articles = {"id": "Q1", "sitelinks": {"commonswiki": {"title": "X"}}}
    disambiguation = {
        "id": "Q2",
        "sitelinks": {"enwiki": {"title": "Mercury"}},
        "descriptions": {"en": {"value": "Wikimedia disambiguation page"}},
    }
    assert make_concept(no_articles, catalog, editions, ["en"]) is None
    assert make_concept(disambiguation, catalog, editions, ["en"]) is None


def test_output_is_relay_ready(api, catalog):
    editions = eds(catalog, "pl,cs")
    text = format_candidates(
        "intermittent fasting",
        editions,
        find_candidates(api, catalog, "intermittent fasting", editions),
        CMD,
    )
    assert "pl: NOT COVERED" in text
    assert '"Post" (broader concept: fasting, Q44602)' in text
    assert f"Then run: {CMD} analyze --concepts Q1666254 --editions pl,cs" in text
    assert "add: --proxy pl:Post" in text


def test_proxy_with_space_is_shell_quoted(api, catalog):
    editions = eds(catalog, "de")
    concepts = find_candidates(api, catalog, "Q2731224", editions)  # VOA Learning English
    text = format_candidates("Q2731224", editions, concepts, CMD)
    assert "--proxy 'de:Kontrollierte Sprache'" in text
