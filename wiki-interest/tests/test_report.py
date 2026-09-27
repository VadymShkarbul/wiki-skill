"""narrative.md checks (R3, R3a) and the one-page PDF (R1-R5), on a saved run: no network.

tests/data/run_q3 is spec query 3 ("English language" in pl, cs, uk, de, tr), saved by analyze
on 2026-09-27 with machine-specific paths normalized.
"""

import json
import re
import shutil
from pathlib import Path

import pytest
from wiki_interest import narrative
from wiki_interest.errors import SkillError
from wiki_interest.i18n import languages, words
from wiki_interest.report import render

RUN_Q3 = Path(__file__).parent / "data" / "run_q3"
GOOD = """# Which audiences should our English app research next?

## Bottom line
Attention to English is flat in Turkish (+0.6%) and German (-0.8%) and declining in Polish
(-9.8%), Czech (-10.9%) and Ukrainian (-13.9%). German has the largest audience, about 23,700
views a month.

## Next
- Validate demand in Turkey first.
- Check Germany next: the largest audience, flat over the last 12 months.
"""


@pytest.fixture
def run(tmp_path):
    target = tmp_path / "run"
    shutil.copytree(RUN_Q3, target)
    return target


def write(run, text):
    (run / "narrative.md").write_text(text, encoding="utf-8")


# --- narrative.md ---------------------------------------------------------------------


def test_missing_narrative_writes_the_template(run):
    with pytest.raises(SkillError, match="template was written"):
        narrative.load(run / "narrative.md")
    assert (run / "narrative.md").read_text(encoding="utf-8") == narrative.TEMPLATE


def test_unfilled_template_is_rejected(run):
    write(run, narrative.TEMPLATE)
    with pytest.raises(SkillError, match="placeholders"):
        narrative.load(run / "narrative.md")


def test_sections_are_required(run):
    write(run, "# Title\n\n## Bottom line\nSomething.\n")
    with pytest.raises(SkillError, match="'## Next' list"):
        narrative.load(run / "narrative.md")


def test_parsing(run):
    write(run, GOOD)
    story = narrative.load(run / "narrative.md")
    assert story.title == "Which audiences should our English app research next?"
    assert story.bottom_line.startswith("Attention to English is flat")
    assert (
        story.bullets[1]
        == "Check Germany next: the largest audience, flat over the last 12 months."
    )


def test_abbreviations_are_not_sentence_ends():
    story = narrative.Narrative(
        "T", "Flat in tr (e.g. +0.6%) vs. de. Declining in pl. Fine.", ["b"]
    )
    narrative.check_length(story, Path("narrative.md"))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("title", "x" * 111, "the title has 111 characters"),
        ("bottom_line", "One. Two. Three. Four.", "4 sentences"),
        ("bullets", ["a"] * 5, "5 bullets"),
        ("bullets", ["b" * 221], "bullets [1] are over 220"),
    ],
)
def test_length_budget(field, value, message):
    story = narrative.Narrative("Title", "One sentence.", ["one"])
    setattr(story, field, value)
    with pytest.raises(SkillError, match=re.escape(message)):
        narrative.check_length(story, Path("narrative.md"))


SUMMARY = "cs DECLINING -47.7% [90% range -62.5% to -27.9%] · 23,694 views/month · 11 of 12 months"


@pytest.mark.parametrize(
    "text",
    [
        "Czech fell 47.7%.",  # as shown
        "Czech fell about 48%.",  # rounded
        "The range reaches 63%.",  # 62.5 rounded half up
        "It could be as low as 62%.",  # 62.5 rounded half even
        "About 23,700 views; about 24 000 by another rounding.",  # thousands in two styles
        "Близько 23 700 переглядів; спад \u221247,7%.",  # Ukrainian separators and decimal comma
        "Three editions over 12 months.",  # small counts are always fine
        "It fell 47.7 percent.",  # a shown percentage, written out
        "About 24K views, i.e. 24 thousand; близько 24 тис.",  # magnitude words
    ],
)
def test_shown_and_rounded_numbers_pass(text):
    narrative.check_numbers(narrative.Narrative("T", text, ["b"]), SUMMARY, Path("n.md"))


@pytest.mark.parametrize(
    "text",
    [
        "Czech is 35% ahead.",
        "Growth will reach 20% next year.",
        "Below a 10% bar.",  # a count, never a percentage
        "11% of months fell.",  # "11 of 12 months" is shown, but not as a percentage
        "About 35K views a month.",  # 35,000 was never shown
    ],
)
def test_invented_numbers_are_rejected(text):
    with pytest.raises(SkillError, match="numbers that the analysis did not show") as info:
        narrative.check_numbers(narrative.Narrative("T", text, ["b"]), SUMMARY, Path("n.md"))
    assert "Do not compute new statistics yourself" in info.value.next_step


# --- labels ---------------------------------------------------------------------------


def test_every_language_file_has_every_label():
    assert set(languages()) >= {"en", "uk"}
    for lang in languages():
        assert set(words(lang)) == set(words("en"))


def test_unknown_language():
    with pytest.raises(SkillError, match="No report labels for language 'xx'"):
        words("xx")


# --- the PDF --------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "uk"])
def test_renders_one_page(run, lang):
    write(run, GOOD)
    pdf = render(run, lang)
    assert pdf.read_bytes().startswith(b"%PDF")
    assert pdf.stat().st_size > 50_000  # both charts are embedded


def test_invented_number_blocks_the_pdf(run):
    write(run, GOOD.replace("about 23,700", "about 35,000"))
    with pytest.raises(SkillError):
        render(run, "en")
    assert not (run / "report.pdf").exists()


def test_not_a_run_folder(tmp_path):
    with pytest.raises(SkillError, match="not an analyze run folder"):
        render(tmp_path, "en")


def test_many_editions_and_notes_still_fit_one_page(run):
    data = json.loads((run / "analysis.json").read_text(encoding="utf-8"))
    extra = []
    for i, edition in enumerate(data["editions"] * 3):
        copy = json.loads(json.dumps(edition))
        copy["code"] = f"x{i}"
        copy["caveats"] = [f"long caveat number {n} " * 4 for n in range(3)]
        extra.append(copy)
    data["editions"] = extra  # 15 editions, 45 caveats
    data["params"]["editions"] = [e["code"] for e in extra]
    (run / "analysis.json").write_text(json.dumps(data), encoding="utf-8")
    write(run, GOOD)
    assert render(run, "en").exists()  # render raises if the page overflows


# --- review fixes ---------------------------------------------------------------------


def test_wrapped_bullet_is_one_bullet(run):
    write(
        run,
        GOOD.replace(
            "- Validate demand in Turkey first.",
            "- Validate demand in Turkey first: stable attention\n  and a clear lead.",
        ),
    )
    story = narrative.load(run / "narrative.md")
    assert story.bullets[0] == "Validate demand in Turkey first: stable attention and a clear lead."
    assert len(story.bullets) == 2


def test_arrows_and_less_than_are_not_placeholders(run):
    write(
        run,
        GOOD.replace(
            "- Validate demand in Turkey first.",
            "- Skip editions with <100 views/month.\n- tr vs de -> no clear difference",
        ),
    )
    assert len(narrative.load(run / "narrative.md").bullets) == 3


def test_user_numbers_are_allowed_only_when_declared():
    story = narrative.Narrative("Which editions grow faster than 15% a year?", "None do.", ["b"])
    with pytest.raises(SkillError, match="'15'"):
        narrative.check_numbers(story, SUMMARY, Path("n.md"))
    narrative.check_numbers(story, SUMMARY, Path("n.md"), user_numbers=[15])


def test_paths_and_run_ids_in_the_summary_do_not_whitelist_numbers():
    summary = SUMMARY + "\nSaved: /home/me/app35/runs/20260927-082914-8ae740\nNext: run x"
    with pytest.raises(SkillError, match="'35'"):
        narrative.check_numbers(narrative.Narrative("T", "35% faster.", ["b"]), summary, Path("n"))


def test_old_run_folder_asks_for_a_new_analyze(run):
    (run / "summary.txt").unlink()
    write(run, GOOD)
    with pytest.raises(SkillError, match="older version") as info:
        render(run, "en")
    assert "analyze --concepts Q1860" in info.value.next_step


def test_big_baskets_list_two_titles_and_fit(run):
    data = json.loads((run / "analysis.json").read_text(encoding="utf-8"))
    for edition in data["editions"]:
        edition["articles"] = [dict(edition["articles"][0], title=f"Article {n}") for n in range(6)]
    (run / "analysis.json").write_text(json.dumps(data), encoding="utf-8")
    write(run, GOOD)
    assert render(run, "en").exists()


def test_max_length_narrative_with_8_editions_fits(run):
    """Review fix: text within the budgets plus a full table used to overflow the page."""
    data = json.loads((run / "analysis.json").read_text(encoding="utf-8"))
    editions = [
        dict(json.loads(json.dumps(e)), code=f"x{i}") for i, e in enumerate(data["editions"] * 2)
    ]
    data["editions"] = editions[:8]
    data["params"]["editions"] = [e["code"] for e in editions[:8]]
    (run / "analysis.json").write_text(json.dumps(data), encoding="utf-8")
    sentence = (
        "Attention to English is flat in Turkish and German but declining in Polish, Czech "
        "and Ukrainian over the last year"
    )
    bottom = ". ".join([sentence[:155]] * 3) + "."
    bullet = ("Validate demand in Turkey first: a stable audience and a clear lead, " * 4)[:219]
    title = "Which language audiences should our English-learning app research next, and why?"
    write(run, f"# {title}\n\n## Bottom line\n{bottom[:479]}\n\n## Next\n" + f"- {bullet}\n" * 4)
    assert render(run, "en").exists()
