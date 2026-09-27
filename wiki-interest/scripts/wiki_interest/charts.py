"""Charts A (trend) and B (growth with its 90% range), decisions R2, R2a and R5.

Both charts are drawn from analysis.json alone, so `report` can redraw them in the report's
language from a saved run, with no network. Colors follow the dataviz reference palette,
validated with its checker:
- chart A: categorical slots in fixed order, one per edition in the user's --editions order
  (color follows the edition, never its rank); every line is also labeled at its end;
- chart B: a polarity encoding: blue = growing, orange = declining, neutral gray = no clear
  change (no red/green). Each row also states its verdict in words.
Titles state the finding. Sized for half the width of an A4 page.
"""

import math
import textwrap
from itertools import pairwise
from typing import IO, Any

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt

from wiki_interest.timeseries import month_range, shift_month

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
DIRECTION = {"growing": "#2a78d6", "declining": "#eb6834", "no clear change": "#898781"}
SURFACE, INK, INK_2, MUTED, GRID, BASELINE = (
    "#ffffff",  # white, like the report page (R5: no off-white panels)
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
MAX_LINES = len(SERIES)


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


def _title(ax: plt.Axes, text: str) -> None:
    ax.set_title(textwrap.fill(text, TITLE_WIDTH), loc="left", color=INK)


def _finite(x: float | None) -> bool:
    return x is not None and math.isfinite(x)


def name(edition: dict[str, Any], words: dict[str, str]) -> str:
    """Edition label on charts; a proxy is marked where the reader sees the number."""
    proxy = any(a["proxy"] for a in edition["articles"])
    return f"{edition['code']} ({words['proxy']})" if proxy else edition["code"]


def user_order(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Editions in the user's --editions order, so colors follow the edition, never its rank."""
    position = {code: i for i, code in enumerate(data["params"]["editions"])}
    return sorted(data["editions"], key=lambda e: position.get(e["code"], len(position)))


def trend_title(data: dict[str, Any], words: dict[str, str]) -> str:
    """Finding for chart A: the biggest year-over-year moves."""
    moved = sorted(
        (e for e in data["editions"] if _finite(e["growth"])), key=lambda e: -abs(e["growth"])
    )
    if not moved:
        return words["no_trend"]
    moves = ", ".join(f"{e['code']} {e['growth'] * 100:+.0f}%" for e in moved[:3])
    months = len(month_range(*data["window"]["current"]))
    return words["trend_title"].format(n=months, moves=moves)


def growth_title(data: dict[str, Any], words: dict[str, str]) -> str:
    """Finding for chart B: which editions show a clear change."""
    by_direction: dict[str, list[str]] = {}
    for e in data["editions"]:
        by_direction.setdefault(e["verdict"]["direction"], []).append(e["code"])
    clear = [
        f"{', '.join(codes)} {words[direction]}"
        for direction in ("growing", "declining")
        if (codes := by_direction.get(direction))
    ]
    if not clear:
        return words["no_clear_change_title"]
    return words["clear_change"].format(items="; ".join(clear))


def rolling_index(edition: dict[str, Any], window: list[str]) -> dict[str, float]:
    """12-month rolling share, indexed to 100 at the first plotted month."""
    share = {row["month"]: row["share_per_million"] for row in edition["monthly"]}
    start = edition["data_from"]
    rolled = {}
    for month in window:
        span = month_range(shift_month(month, -11), month)
        if start and span[0] >= start and all(share.get(m) is not None for m in span):
            rolled[month] = sum(share[m] for m in span) / 12
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


def _spike_driven(edition: dict[str, Any]) -> bool:
    return any(r.startswith("spike-driven") for r in edition["verdict"]["reasons"])


def draw_trend(data: dict[str, Any], target: str | IO[bytes], words: dict[str, str]) -> None:
    window = month_range(*data["window"]["months"])
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=SURFACE)
    _style(ax)
    ends = []
    for slot, edition in enumerate(user_order(data)[:MAX_LINES]):
        index = rolling_index(edition, window)
        if not index:
            continue
        months = list(index)
        x = [window.index(m) for m in months]
        color = SERIES[slot]
        label = name(edition, words)
        ax.plot(x, list(index.values()), color=color, linewidth=1.5, label=label)
        spikes = {s["date"][:7] for s in edition["spike_days"]} if _spike_driven(edition) else set()
        marks = [(window.index(m), index[m]) for m in months if m in spikes]
        if marks:
            ax.plot(
                *zip(*marks, strict=True),
                "o",
                color=color,
                markersize=4.5,
                markeredgecolor=SURFACE,
                markeredgewidth=1.0,
            )
        ends.append((x[-1], index[months[-1]], label))
    ax.axhline(100, color=BASELINE, linewidth=0.8)
    if ends:
        low, high = ax.get_ylim()
        placed = _spread([y for _, y, _ in ends], LABEL_GAP * (high - low))
        for (x_end, _, label), y in zip(ends, placed, strict=True):
            ax.annotate(
                label,
                (x_end, y),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                color=INK_2,
                fontsize=7,
            )
        if len(ends) > 1:
            ax.legend(
                frameon=False,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.16),
                fontsize=6.5,
                ncols=min(len(ends), MAX_LINES),
                handlelength=1.2,
                columnspacing=1.0,
            )
    ticks = [i for i, m in enumerate(window) if m.endswith(("-01", "-07"))]
    ax.set_xticks(ticks, [window[i] for i in ticks])
    ax.set_xlim(-0.5, len(window) + 1.5)
    _title(ax, trend_title(data, words))
    ax.set_ylabel(words["trend_axis"])
    fig.tight_layout()
    fig.savefig(target, facecolor=SURFACE, format="png")
    plt.close(fig)


def draw_growth(data: dict[str, Any], target: str | IO[bytes], words: dict[str, str]) -> None:
    editions = list(reversed(data["editions"][:MAX_LINES]))  # first result at the top
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=SURFACE)
    _style(ax)
    ax.grid(visible=False)
    ax.axvline(0, color=BASELINE, linewidth=0.8)
    bounds = [abs(v) for e in editions if _finite(e["growth"]) for v in e["interval"]]
    reach = max([*bounds, 0.1])
    for y, e in enumerate(editions):
        direction = e["verdict"]["direction"]
        if not _finite(e["growth"]):
            ax.text(0, y, words["insufficient data"], ha="center", va="center", color=MUTED)
            continue
        color = DIRECTION[direction]
        low, high = e["interval"]
        ax.plot([low * 100, high * 100], [y, y], color=color, linewidth=1.5)
        ax.plot(
            e["growth"] * 100,
            y,
            "o",
            color=color,
            markersize=5.5,
            markeredgecolor=SURFACE,
            markeredgewidth=1.0,
        )
        ax.annotate(
            f"{e['growth'] * 100:+.1f}%  {words[direction]}",
            (1.03, y),
            xycoords=("axes fraction", "data"),
            va="center",
            ha="left",
            color=INK_2,
            fontsize=6.5,
            annotation_clip=False,
        )
    ax.set_yticks(range(len(editions)), [name(e, words) for e in editions])
    ax.set_ylim(-0.7, len(editions) - 0.3)
    ax.set_xlim(-reach * 100 * 1.1, reach * 100 * 1.1)
    ax.xaxis.set_major_locator(mpl.ticker.MaxNLocator(nbins=4, symmetric=True))
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%")
    _title(ax, growth_title(data, words))
    ax.set_xlabel(words["growth_axis"])
    # Fixed margins: the verdict labels live in the right margin, outside the plot, and
    # tight_layout would count them as plot content and squeeze the axes.
    fig.subplots_adjust(left=0.1, right=0.6, top=0.84, bottom=0.2)
    fig.savefig(target, facecolor=SURFACE, format="png")
    plt.close(fig)
