"""The report step: a one-page A4 PDF from a run folder (decisions R1-R5).

Inputs are the run folder's analysis.json and summary.txt (both from analyze) and the model's
narrative.md. Code writes every number, the table, the charts, the caveats and the footer; the
model writes only the title, the bottom line and the "research next" bullets, which are checked
first (narrative.py). The layout follows the design exclusions in R5: white page, one accent,
no numbered or pill labels, no monospace, section headings in plain bold.
"""

import io
import json
import math
from pathlib import Path
from typing import Any

import matplotlib as mpl
from fpdf import FPDF, FontFace

from wiki_interest import narrative
from wiki_interest.charts import SIZE, draw_growth, draw_trend
from wiki_interest.errors import SkillError
from wiki_interest.i18n import words
from wiki_interest.timeseries import month_range

FONT_DIR = Path(mpl.get_data_path()) / "fonts" / "ttf"
FONT = "DejaVu"  # bundled with matplotlib; covers Latin, Cyrillic and Greek
PAGE_W, PAGE_H, MARGIN = 210, 297, 14
CONTENT = PAGE_W - 2 * MARGIN
GAP = 4
CHART_W = (CONTENT - GAP) / 2
CHART_H = CHART_W * SIZE[1] / SIZE[0]
FOOTER_H = 9
MAX_ROWS = 8
MAX_TITLES = 2  # article titles listed per edition; a basket may have more
INK, INK_2, MUTED, RULE = (11, 11, 11), (82, 81, 78), (137, 135, 129), (225, 224, 217)
COLUMNS = (
    ("col_edition", 24),
    ("col_article", 32),
    ("col_views", 21),
    ("col_growth", 36),
    ("col_verdict", 25),
    ("col_confidence", 21),
    ("col_segment", 23),
)


def _pct(x: float | None) -> str:
    return f"{x * 100:+.1f}%" if x is not None and math.isfinite(x) else "-"


class _Page(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4", unit="mm")
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=MARGIN)
        self.add_font(FONT, "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_page()

    def text_block(  # noqa: PLR0913 - typography knobs of one paragraph
        self,
        text: str,
        size: float,
        *,
        bold: bool = False,
        color: tuple[int, int, int] = INK,
        height: float = 0,
        gap: float = 0.0,
    ) -> None:
        self.set_font(FONT, "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(
            CONTENT, height or size * 0.5, text, align="L", new_x="LMARGIN", new_y="NEXT"
        )
        self.ln(gap)

    def heading(self, text: str) -> None:
        self.ln(2)
        self.text_block(text, 9.5, bold=True, height=5.5)
        self.set_draw_color(*RULE)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(1.5)


def _table(pdf: _Page, data: dict[str, Any], w: dict[str, Any]) -> None:
    editions = data["editions"]
    rows = editions[:MAX_ROWS]
    pdf.set_font(FONT, "", 7.5)
    pdf.set_text_color(*INK)
    with pdf.table(
        col_widths=[width for _, width in COLUMNS],
        first_row_as_headings=True,
        headings_style=FontFace(emphasis="BOLD", color=INK_2),
        borders_layout="HORIZONTAL_LINES",
        line_height=4.2,
        text_align="LEFT",
        padding=(1, 1, 1, 0),
    ) as table:
        header = table.row()
        for key, _ in COLUMNS:
            header.cell(w[key])
        for e in rows:
            direction = e["verdict"]["direction"]
            confidence = e["verdict"]["confidence"]
            low, high = e["interval"]
            growth = (
                f"{_pct(e['growth'])} [{_pct(low)}, {_pct(high)}]"
                if e["growth"] is not None
                else "-"
            )
            names = [
                f"{a['title']} ({w['proxy']})" if a["proxy"] else a["title"] for a in e["articles"]
            ]
            titles = ", ".join(names[:MAX_TITLES])
            if len(names) > MAX_TITLES:
                titles += f" +{len(names) - MAX_TITLES}"
            segment = e["quadrant"] if e["quadrant"] in w else ""
            row = table.row()
            row.cell(f"{e['code']} ({e['name']})")
            row.cell(titles)
            row.cell(f"{e['median_views_per_month'] or 0:,.0f}")
            row.cell(growth)
            row.cell(w[direction])  # text stays in ink; chart B carries the color
            row.cell(w[confidence] if confidence else "-")
            row.cell(w[segment] if segment else "")
        for e in data["not_covered"]:
            row = table.row()
            row.cell(f"{e['code']} ({e['name']})")
            row.cell("-")
            row.cell("")
            row.cell("")
            row.cell(w["not covered"], style=FontFace(color=MUTED))
            row.cell("")
            row.cell("")
    if len(editions) > MAX_ROWS:
        pdf.text_block(w["rows_hidden"].format(shown=MAX_ROWS, total=len(editions)), 7, color=MUTED)


def _comparisons(pdf: _Page, data: dict[str, Any], w: dict[str, Any]) -> None:
    lines = [
        w["comparison"].format(
            a=d["leader"],
            b=d["other"],
            gap=f"{d['gap'] * 100:.1f}",
            clear=w["clear"] if d["clear"] else w["unclear"],
        )
        for d in data["comparison"]
    ]
    if lines:
        pdf.ln(1)
        pdf.text_block(" · ".join(lines), 7.5, color=INK_2, height=3.8)


def _charts(pdf: _Page, data: dict[str, Any], w: dict[str, Any]) -> None:
    pdf.ln(2)
    top = pdf.get_y()
    for i, draw in enumerate((draw_trend, draw_growth)):
        buffer = io.BytesIO()
        draw(data, buffer, w)
        buffer.seek(0)
        pdf.image(buffer, x=MARGIN + i * (CHART_W + GAP), y=top, w=CHART_W, h=CHART_H)
    pdf.set_y(top + CHART_H + 1)


def _notes(data: dict[str, Any], w: dict[str, Any]) -> list[str]:
    """Limitations in priority order; the first one is never cut."""
    method = w["method"]
    edition_notes = [f"{e['code']}: {c}" for e in data["editions"] for c in e["caveats"]]
    return [method[0], *edition_notes, *data["caveats"], *method[1:]]


def _limitations(pdf: _Page, data: dict[str, Any], w: dict[str, Any]) -> None:
    pdf.heading(w["limitations"])
    pdf.set_font(FONT, "", 7)
    pdf.set_text_color(*INK_2)
    bottom = PAGE_H - MARGIN - FOOTER_H
    notes = _notes(data, w)
    line = 3.4
    for i, note in enumerate(notes):
        text = f"• {note}"
        height = pdf.multi_cell(CONTENT, line, text, align="L", dry_run=True, output="HEIGHT")
        left = len(notes) - i - 1
        reserve = line if left else 0
        if pdf.get_y() + height + reserve > bottom and i:
            pdf.multi_cell(
                CONTENT,
                line,
                w["more_notes"].format(n=len(notes) - i),
                align="L",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            return
        pdf.multi_cell(CONTENT, line, text, align="L", new_x="LMARGIN", new_y="NEXT")


def _footer(pdf: _Page, data: dict[str, Any], w: dict[str, Any]) -> None:
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(PAGE_H - MARGIN - FOOTER_H + 2)
    pdf.set_draw_color(*RULE)
    pdf.line(MARGIN, pdf.get_y() - 1, PAGE_W - MARGIN, pdf.get_y() - 1)
    pdf.text_block(
        w["footer"].format(date=data["data_through"], rerun=data["rerun"]), 6, color=MUTED, height=3
    )


def render(run_dir: Path, lang: str, user_numbers: list[float] | None = None) -> Path:
    if not (run_dir / "analysis.json").exists():
        raise SkillError(
            f"{run_dir} is not an analyze run folder (no analysis.json).",
            "Run analyze first, then pass the folder from its 'Saved:' line to --run.",
        )
    data = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    if "params" not in data or not (run_dir / "summary.txt").exists():
        raise SkillError(
            f"{run_dir} was made by an older version of wiki-interest.",
            f"Run its analyze command again ({data.get('rerun', 'see analysis.json')}), then "
            "pass the new run folder to report.",
        )
    summary = (run_dir / "summary.txt").read_text(encoding="utf-8")
    path = run_dir / "narrative.md"
    story = narrative.load(path)
    narrative.check_length(story, path)
    narrative.check_numbers(story, summary, path, user_numbers)
    w = words(lang)

    pdf = _Page()
    pdf.text_block(story.title, 15, bold=True, height=7)
    codes = ", ".join(e["code"] for e in data["editions"]) or "-"
    months = len(month_range(*data["window"]["current"]))
    pdf.text_block(
        w["meta"].format(editions=codes, n=months, date=data["data_through"]), 8, color=MUTED, gap=1
    )
    pdf.heading(w["bottom_line"])
    pdf.text_block(story.bottom_line, 9.5, height=5)
    pdf.heading(w["verdicts"])
    _table(pdf, data, w)
    _comparisons(pdf, data, w)
    _charts(pdf, data, w)
    if pdf.page_no() > 1:
        raise SkillError(
            "The analysis has too many editions or concepts to fit its table and charts on one "
            "page.",
            "Re-run analyze with fewer editions (at most 8 are shown) or fewer concepts, or "
            "share analysis.json and the charts instead of a PDF.",
        )
    pdf.heading(w["research_next"])
    for bullet in story.bullets:
        pdf.text_block(f"• {bullet}", 9, height=4.6)
    _limitations(pdf, data, w)
    _footer(pdf, data, w)
    if pdf.page_no() > 1:
        raise SkillError(
            "The report does not fit on one page.",
            f"Shorten the bottom line and bullets in {path}, then re-run the same report command.",
        )
    out = run_dir / "report.pdf"
    pdf.output(str(out))
    return out
