"""The model's part of the report: narrative.md, and the checks it must pass (R3, R3a).

The model writes three things: a title, a bottom line, and "what to research next" bullets.
Everything else in the report comes from code. Before rendering, the narrative is rejected if
it uses a number that the analyze summary did not show (rounding is allowed), or if it is
longer than the one-page layout allows. Each rejection ends with a Next step.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from wiki_signal.errors import SkillError

TITLE_MAX = 110
BOTTOM_MAX_CHARS = 480  # about four lines at 9.5 pt
BOTTOM_MAX_SENTENCES = 3
BULLETS_MAX = 4
BULLET_MAX_CHARS = 220  # two lines at 9 pt
COUNTS = set(range(13))  # "3 editions", "12 months"; never percentages (see check_numbers)
SHOWN_UNKNOWN = 5

TEMPLATE = """# <the user's question, in their words and language>

## Bottom line
<Up to 3 sentences that answer the question. Use only numbers from the analyze summary.>

## Next
- <What to research next, and why. Up to 4 bullets.>
"""

NUMBER = re.compile(
    r"(?<![\w.])[-+\u2212\u2013]?"
    r"(?:\d{1,3}(?:[, \u00a0\u202f]\d{3}(?!\d))+|\d+)"  # 23 700 / 23,700 / 23700
    r"(?:[.,]\d+)?"
)
# "85K", "1.2 million", "23 тис.": the writer rounded to thousands or millions
MAGNITUDE = re.compile(
    r"\s?(k|K|thousand|тис\.?|тисяч\w*|M|mln|million|млн\.?)(?![\w])", re.UNICODE
)
MAGNITUDES = {
    "k": 1e3,
    "thousand": 1e3,
    "тис": 1e3,
    "тисяч": 1e3,
    "m": 1e6,
    "mln": 1e6,
    "million": 1e6,
    "млн": 1e6,
}
PLACEHOLDER = re.compile(r"<[^<>\n]{3,}>")  # one line: "<100 ... ->" is not a placeholder
ABBREVIATIONS = re.compile(
    r"\b(?:e\.g|i\.e|vs|etc|approx|cf|incl|No|т\.зв|напр|тис|млн)\.", re.IGNORECASE
)
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")


@dataclass
class Narrative:
    title: str
    bottom_line: str
    bullets: list[str]


def _template_error(path: Path, problem: str) -> SkillError:
    return SkillError(
        f"{path} {problem}.",
        f"Edit {path}: replace each <...> placeholder with your text (headings '# ', "
        "'## Bottom line' and '## Next' stay in English; the text can be in any language). "
        "Then re-run the same report command.",
    )


def load(path: Path) -> Narrative:
    """Parse narrative.md. When it doesn't exist yet, write the template and say so."""
    if not path.exists():
        path.write_text(TEMPLATE, encoding="utf-8")
        raise _template_error(path, "did not exist, so a template was written there")
    text = path.read_text(encoding="utf-8")
    if PLACEHOLDER.search(text):
        raise _template_error(path, "still contains template placeholders")
    title, section, bottom, bullets = "", "", [], []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            section = line[3:].strip().casefold()
        elif line and section == "bottom line":
            bottom.append(line)
        elif line and section == "next":
            if line[0] in "-*\u2022" or not bullets:
                bullets.append(line.lstrip("-*\u2022 ").strip())
            else:  # a hard-wrapped bullet continues on the next line
                bullets[-1] = f"{bullets[-1]} {line}"
    if not (title and bottom and bullets):
        raise _template_error(path, "needs a '# ' title, a '## Bottom line' and a '## Next' list")
    return Narrative(title, " ".join(bottom), bullets)


def check_length(n: Narrative, path: Path) -> None:
    problems = []
    if len(n.title) > TITLE_MAX:
        problems.append(f"the title has {len(n.title)} characters (max {TITLE_MAX})")
    sentences = len(SENTENCE_END.findall(ABBREVIATIONS.sub("", n.bottom_line) + " "))
    if sentences > BOTTOM_MAX_SENTENCES or len(n.bottom_line) > BOTTOM_MAX_CHARS:
        problems.append(
            f"the bottom line has {sentences} sentences and {len(n.bottom_line)} characters "
            f"(max {BOTTOM_MAX_SENTENCES} and {BOTTOM_MAX_CHARS})"
        )
    if len(n.bullets) > BULLETS_MAX:
        problems.append(f"there are {len(n.bullets)} bullets (max {BULLETS_MAX})")
    long = [i + 1 for i, b in enumerate(n.bullets) if len(b) > BULLET_MAX_CHARS]
    if long:
        problems.append(f"bullets {long} are over {BULLET_MAX_CHARS} characters")
    if problems:
        raise SkillError(
            f"{path.name} is too long for the one-page report: {'; '.join(problems)}.",
            f"Shorten {path}, then re-run the same report command.",
        )


def parse_number(token: str) -> float:
    digits = (
        token.lstrip("+-\u2212\u2013").replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    )
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", digits):
        digits = digits.replace(",", "")  # thousands separators
    return float(digits.replace(",", "."))  # decimal comma (uk, pl, cs)


def _scaled(text: str, match: re.Match[str]) -> float:
    """The number's value, including a magnitude word right after it (85K -> 85000)."""
    value = parse_number(match.group())
    suffix = MAGNITUDE.match(text, match.end())
    if suffix:
        word = suffix.group(1).rstrip(".").casefold()
        word = "тисяч" if word.startswith("тисяч") else word
        value *= MAGNITUDES[word]
    return value


def _is_percent(text: str, end: int) -> bool:
    return text[end : end + 2].lstrip().startswith("%")


def _roundings(value: float) -> set[float]:
    """The ways a writer may legitimately round a shown number: 47.7 -> 48 or 47.7."""
    places = (2, 1, 0, -1, -2, -3) if value >= 100 else (2, 1, 0)  # noqa: PLR2004
    half_even = {round(value, d) for d in places}  # Python's round: 62.5 -> 62
    half_up = {round(math.floor(value * 10**d + 0.5) / 10**d, 6) for d in places}  # 62.5 -> 63
    return {round(v, 6) for v in half_even} | half_up


RUN_ID = re.compile(r"\d{8}-\d{6}-[0-9a-f]{6}")
PLUMBING = ("Saved:", "Re-run:", "Next:")


def shown_numbers(summary: str) -> str:
    """The summary without paths, commands and the run id, whose digits are not findings."""
    lines = [line for line in summary.splitlines() if not line.startswith(PLUMBING)]
    return RUN_ID.sub("", "\n".join(lines))


def unknown_numbers(text: str, summary: str, user_numbers: list[float] | None = None) -> list[str]:
    """Numbers in ``text`` that the summary did not show and the user did not give, each with
    a little context. Allows normal rounding (R3a).

    Unit-aware: a percentage must match a percentage the summary showed ("10 of 12 months"
    does not license "10%"). Plain numbers may match either kind ("45.5 percent").
    Also used by the eval grader to check a model's final answer.
    """
    percents: set[float] = set()
    plain: set[float] = set()
    shown = shown_numbers(summary)
    for match in NUMBER.finditer(shown):
        value = abs(parse_number(match.group()))
        (percents if _is_percent(shown, match.end()) else plain).update(_roundings(value))
    for value in user_numbers or []:
        percents |= _roundings(abs(value))
    plain |= percents
    unknown = []
    for match in NUMBER.finditer(text):
        token, value = match.group(), round(abs(_scaled(text, match)), 6)
        if _is_percent(text, match.end()):
            ok = value in percents
        else:
            ok = value in plain or value in COUNTS
        if not ok:
            start = match.start()
            unknown.append(
                f"{token!r} in \u201c\u2026{text[max(0, start - 25) : start + 25]}\u2026\u201d"
            )
    return unknown


def check_numbers(
    n: Narrative, summary: str, path: Path, user_numbers: list[float] | None = None
) -> None:
    """Every number in the narrative must be one the analyze summary showed, or one the user
    gave (a threshold or goal from their question)."""
    text = " ".join([n.title, n.bottom_line, *n.bullets])
    unknown = unknown_numbers(text, summary, user_numbers)
    if unknown:
        listed = "; ".join(unknown[:SHOWN_UNKNOWN])
        more = f" (and {len(unknown) - SHOWN_UNKNOWN} more)" if len(unknown) > SHOWN_UNKNOWN else ""
        raise SkillError(
            f"{path.name} uses numbers that the analysis did not show: {listed}{more}.",
            "Use only numbers from the analyze summary (rounding is fine) or remove them, then "
            "re-run the same report command. Do not compute new statistics yourself. If a "
            "number came from the user (e.g. their growth threshold), pass it with "
            "--user-numbers.",
        )
