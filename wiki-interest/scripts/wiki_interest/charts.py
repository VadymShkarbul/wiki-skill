"""Charts A (trend) and B (growth with its 90% range), decisions R2 and R5.

Colors follow the dataviz reference palette, validated with its checker:
- chart A: categorical slots in fixed order, one per edition (color follows the edition);
  every line is also labeled at its end, so identity never relies on color alone;
- chart B: a polarity encoding: blue = growing, orange = declining, neutral gray = no clear
  change (no red/green). Each row also states its verdict in words.
Titles state the finding. Sized for half the width of an A4 page.
"""

import math
import textwrap
from itertools import pairwise

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from wiki_interest.analysis import Analysis, EditionResult
from wiki_interest.timeseries import month_range, shift_month

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DIRECTION = {"growing": "#2a78d6", "declining": "#eb6834", "no clear change": "#898781"}
SURFACE, INK, INK_2, MUTED, GRID, BASELINE = (
    "#fcfcfb",
    "#0b0b0b",
    "#52514e",
    "#898781",
    "#e1e0d9",
    "#c3c2b7",
)
SIZE = (3.6, 2.7)  # inches; two side by side fit an A4 page
DPI = 220
LABEL_GAP = 0.055  # minimum vertical gap between end labels, as a share of the y range
TITLE_WIDTH = 52  # characters per title line at this size

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",  # covers Latin, Cyrillic and Greek
        "font.size": 7,
        "axes.titlesize": 8,
        "axes.edgecolor": BASELINE,
        "axes.labelcolor": INK_2,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "text.color": INK,
    }
)


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def _moved(x: float) -> str:
    return f"{'rose' if x > 0 else 'fell'} {abs(x) * 100:.0f}%"


def trend_title(analysis: Analysis) -> str:
    """Finding for chart A: the biggest year-over-year moves."""
    moved = [r for r in analysis.results if math.isfinite(r.growth)]
    moved.sort(key=lambda r: -abs(r.growth))
    if not moved:
        return "Not enough data for a trend"
    parts = ", ".join(f"{r.edition.code} {_moved(r.growth)}" for r in moved[:3])
    return f"{parts} in the last {len(analysis.current)} months vs a year earlier"


def growth_title(analysis: Analysis) -> str:
    """Finding for chart B: which editions show a clear change."""
    by_direction: dict[str, list[str]] = {}
    for r in analysis.results:
        by_direction.setdefault(r.verdict.direction, []).append(r.edition.code)
    clear = [
        f"{', '.join(codes)} {direction}"
        for direction in ("growing", "declining")
        if (codes := by_direction.get(direction))
    ]
    return "Clear change: " + "; ".join(clear) if clear else "No edition shows a clear change"


def edition_order(analysis: Analysis) -> list[EditionResult]:
    """Results in the user's --editions order, so colors follow the edition, never its rank."""
    position = {e.code: i for i, e in enumerate(analysis.editions)}
    return sorted(analysis.results, key=lambda r: position[r.edition.code])


def color_of(analysis: Analysis, result: EditionResult) -> str:
    covered = [r.edition.code for r in edition_order(analysis)]
    return SERIES[covered.index(result.edition.code) % len(SERIES)]


def name(result: EditionResult) -> str:
    """Edition label on charts; a proxy is marked where the reader sees the number."""
    return (
        f"{result.edition.code} (proxy)"
        if any(a.proxy for a in result.articles)
        else (result.edition.code)
    )


def _title(ax: plt.Axes, text: str) -> None:
    ax.set_title(textwrap.fill(text, TITLE_WIDTH), loc="left", color=INK)


def rolling_index(result: EditionResult, window: list[str]) -> dict[str, float]:
    """12-month rolling share, indexed to 100 at the first plotted month."""
    rolled = {}
    for month in window:
        span = month_range(shift_month(month, -11), month)
        if (
            result.data_from
            and span[0] >= result.data_from
            and all(m in result.share for m in span)
        ):
            rolled[month] = sum(result.share[m] for m in span) / 12
    if not rolled:
        return {}
    base = next(iter(rolled.values()))
    return {m: v / base * 100 for m, v in rolled.items()} if base > 0 else {}


def _spread(ys: list[float], gap: float) -> list[float]:
    """Nudge end labels apart so they don't overlap; keeps their order."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    placed = list(ys)
    for prev, cur in pairwise(order):
        placed[cur] = max(placed[cur], placed[prev] + gap)
    return placed


def draw_trend(analysis: Analysis, path: str) -> None:
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=SURFACE)
    _style(ax)
    lines = []
    for result in edition_order(analysis)[: len(SERIES)]:
        index = rolling_index(result, analysis.window)
        if not index:
            continue
        months = list(index)
        x = [analysis.window.index(m) for m in months]
        color = color_of(analysis, result)
        ax.plot(x, list(index.values()), color=color, linewidth=1.5, label=name(result))
        spike_driven = any(r.startswith("spike-driven") for r in result.verdict.reasons)
        spike_months = {d[:7] for d, _ in result.spike_days} if spike_driven else set()
        marks = [(analysis.window.index(m), index[m]) for m in months if m in spike_months]
        if marks:
            ax.plot(
                *zip(*marks, strict=True),
                "o",
                color=color,
                markersize=4.5,
                markeredgecolor=SURFACE,
                markeredgewidth=1.0,
            )
        lines.append((x[-1], index[months[-1]], name(result)))
    ax.axhline(100, color=BASELINE, linewidth=0.8)
    if lines:
        low, high = ax.get_ylim()
        placed = _spread([y for _, y, _ in lines], LABEL_GAP * (high - low))
        for (x_end, _, code), y in zip(lines, placed, strict=True):
            ax.annotate(
                code,
                (x_end, y),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                color=INK_2,
                fontsize=7,
            )
        if len(lines) > 1:
            ax.legend(
                frameon=False,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.16),
                fontsize=6.5,
                ncols=min(len(lines), 8),
                handlelength=1.2,
                columnspacing=1.0,
            )
    ticks = [i for i, m in enumerate(analysis.window) if m.endswith(("-01", "-07"))]
    ax.set_xticks(ticks, [analysis.window[i] for i in ticks])
    ax.set_xlim(-0.5, len(analysis.window) + 1.5)
    _title(ax, trend_title(analysis))
    ax.set_ylabel("12-month share of attention (start = 100)")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def draw_growth(analysis: Analysis, path: str) -> None:
    results = list(reversed(analysis.results))  # first result at the top
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=SURFACE)
    _style(ax)
    ax.grid(visible=False)
    ax.axvline(0, color=BASELINE, linewidth=0.8)
    finite = [r for r in results if math.isfinite(r.growth)]
    reach = max([abs(v) for r in finite for v in (r.interval.low, r.interval.high)] + [0.1])
    for y, r in enumerate(results):
        if not math.isfinite(r.growth):
            ax.text(0, y, "insufficient data", ha="center", va="center", color=MUTED, fontsize=6.5)
            continue
        color = DIRECTION[r.verdict.direction]
        ax.plot([r.interval.low * 100, r.interval.high * 100], [y, y], color=color, linewidth=1.5)
        ax.plot(
            r.growth * 100,
            y,
            "o",
            color=color,
            markersize=5.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.0,
        )
        ax.annotate(
            f"{r.growth * 100:+.1f}%  {r.verdict.direction}",
            (1.03, y),
            xycoords=("axes fraction", "data"),
            va="center",
            ha="left",
            color=INK_2,
            fontsize=6.5,
            annotation_clip=False,
        )
    ax.set_yticks(range(len(results)), [name(r) for r in results])
    ax.set_ylim(-0.7, len(results) - 0.3)
    ax.set_xlim(-reach * 100 * 1.1, reach * 100 * 1.1)
    ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4, symmetric=True))
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%")
    _title(ax, growth_title(analysis))
    ax.set_xlabel("growth vs a year earlier, with its 90% range")
    # Fixed margins: the verdict labels live in the right margin, outside the plot, and
    # tight_layout would count them as plot content and squeeze the axes.
    fig.subplots_adjust(left=0.1, right=0.6, top=0.84, bottom=0.2)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
