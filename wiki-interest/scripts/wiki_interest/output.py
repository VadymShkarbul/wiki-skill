"""analyze output: a relay-ready text summary (I3) plus analysis.json and charts in a run dir.

The summary is written for a small model to pass on: verdict lines are complete sentences
with their numbers, reasons, and caveats, followed by Re-run and Next lines.
"""

import hashlib
import json
import math
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wiki_interest import __version__
from wiki_interest.analysis import Analysis, EditionResult
from wiki_interest.charts import draw_growth, draw_trend
from wiki_interest.i18n import words
from wiki_interest.timeseries import shift_month

RUNS_DIR = "wiki-interest-runs"
TOP_SPIKES = 3
METHOD = [
    "Pageviews measure attention on Wikipedia, not demand or willingness to pay.",
    (
        "Interest is the topic articles' share of all human pageviews in that edition "
        "(views per million), so edition size and edition-wide trends cancel out."
    ),
    "Growth compares each month with the same month a year earlier, which cancels seasonality.",
    (
        "The 90% range comes from resampling those month pairs; with few pairs it can be "
        "slightly too narrow."
    ),
    "Only each article's current title is counted: views of redirects and former titles are not.",
    "Human traffic as classified by Wikimedia (agent=user); some automated traffic may remain.",
]


def pct(x: float) -> str:
    return f"{x * 100:+.1f}%" if math.isfinite(x) else "n/a"


def _num(x: float) -> float | None:
    return round(x, 6) if isinstance(x, float) and math.isfinite(x) else None


def run_id(analysis: Analysis, now: datetime) -> str:
    key = json.dumps(rerun_args(analysis), ensure_ascii=False)
    return f"{now:%Y%m%d-%H%M%S}-{hashlib.sha1(key.encode()).hexdigest()[:6]}"  # noqa: S324 - an id, not security


def rerun_args(analysis: Analysis) -> list[str]:
    args = ["analyze", "--concepts", *(c.qid for c in analysis.concepts)]
    args += ["--editions", ",".join(e.code for e in analysis.editions)]
    args += ["--months", str(analysis.months)]
    for proxy in analysis.proxies:
        args += ["--proxy", proxy]
    if analysis.sort != "growth":
        args += ["--sort", analysis.sort]
    return args


def _edition_json(r: EditionResult) -> dict[str, Any]:
    return {
        "code": r.edition.code,
        "name": r.edition.name,
        "articles": [
            {
                "concept": a.concept.qid,
                "title": a.title,
                "proxy": a.proxy,
                "first_revision": a.created.isoformat() if a.created else None,
                "first_viewed_day": a.first_day.isoformat() if a.first_day else None,
                "probably_renamed_on": (d.isoformat() if (d := a.renamed_hint()) else None),
            }
            for a in r.articles
        ],
        "verdict": {
            "direction": r.verdict.direction,
            "confidence": r.verdict.confidence,
            "reasons": r.verdict.reasons,
        },
        "quadrant": r.quadrant or None,
        "growth": _num(r.growth),
        "interval": [_num(r.interval.low), _num(r.interval.high)],
        "despiked_growth": _num(r.despiked_growth),
        "months_agreeing": r.months_agreeing,
        "pairs": r.pairs,
        "spike_share": _num(r.spike_share),
        "spike_days": [{"date": d, "views": v} for d, v in r.spike_days],
        "trend_per_year": _num(r.trend_per_year),
        "median_views_per_month": _num(r.median_views),
        "mean_share_per_million": _num(r.mean_share),
        "edition_growth": _num(r.edition_growth),
        "seasonal_peak": (
            {"month": r.seasonal_peak[0], "lift": _num(r.seasonal_peak[1])}
            if r.seasonal_peak
            else None
        ),
        "data_from": r.data_from,
        "caveats": r.caveats,
        "monthly": [
            {
                "month": m,
                "views": r.views[m],
                "edition_total": r.total[m],
                "share_per_million": _num(r.share[m]),
            }
            for m in r.months
        ],
    }


def to_json(analysis: Analysis, rid: str, files: dict[str, str], command: str) -> dict[str, Any]:
    current = analysis.current
    return {
        "schema": 1,
        "tool": f"wiki-interest {__version__}",
        "run_id": rid,
        "data_through": analysis.data_through.isoformat(),
        "params": {
            "concepts": [c.qid for c in analysis.concepts],
            "editions": [e.code for e in analysis.editions],
            "months": analysis.months,
            "proxies": analysis.proxies,
            "sort": analysis.sort,
        },
        "concepts": [{"qid": c.qid, "label": c.label} for c in analysis.concepts],
        "window": {
            "months": [analysis.window[0], analysis.window[-1]],
            "current": [current[0], current[-1]],
            "previous": [shift_month(current[0], -12), shift_month(current[-1], -12)],
        },
        "editions": [_edition_json(r) for r in analysis.results],
        "not_covered": [{"code": e.code, "name": e.name} for e in analysis.not_covered],
        "excluded_concepts": analysis.excluded,
        "like_for_like": analysis.like_for_like,
        "comparison": [
            {
                "leader": d.leader,
                "other": d.other,
                "gap": _num(d.growth_gap),
                "interval": [_num(d.interval.low), _num(d.interval.high)],
                "clear": d.clear,
            }
            for d in analysis.differences
        ],
        "caveats": analysis.caveats,
        "method": METHOD,
        "files": files,
        "rerun": f"{command} {shlex.join(rerun_args(analysis))}",
    }


def _month_name(mm: str) -> str:
    return datetime(2000, int(mm), 1).strftime("%B")  # noqa: DTZ001 - only the month name is used


def _edition_lines(r: EditionResult) -> list[str]:
    titles = ", ".join(f"{a.title} (proxy)" if a.proxy else a.title for a in r.articles)
    lines = [f"{r.edition.label()} · {titles}"]
    v = r.verdict
    size = f"{r.median_views:,.0f} views/month"
    if math.isfinite(r.growth):
        confidence = f" · confidence {v.confidence.upper()}" if v.confidence else ""
        quadrant = f" · {r.quadrant}" if r.quadrant else ""
        lines.append(
            f"  {v.direction.upper()} {pct(r.growth)} [90% range {pct(r.interval.low)} to "
            f"{pct(r.interval.high)}]{confidence} · {size}{quadrant}"
        )
    else:
        lines.append(f"  {v.direction.upper()} · {size}")
    lines += [f"  - {reason}" for reason in v.reasons]
    if any(reason.startswith("spike-driven") for reason in v.reasons):
        top = ", ".join(f"{d} ({n:,} views)" for d, n in r.spike_days[:TOP_SPIKES])
        lines.append(f"  - spike days (causes unknown, do not guess): {top}")
    if r.seasonal_peak:
        month, lift = r.seasonal_peak
        lines.append(f"  - seasonal: peaks in {_month_name(month)} ({pct(lift - 1)} vs average)")
    lines += [f"  - caveat: {c}" for c in r.caveats]
    return lines


def format_summary(analysis: Analysis, data: dict[str, Any], out_dir: Path, command: str) -> str:
    current = analysis.current
    concepts = "; ".join(f"{c.qid} {c.label}" for c in analysis.concepts)
    lines = [
        f"Analysis {data['run_id']} · data through {data['data_through']}",
        f"Concepts: {concepts}",
        (
            f"Growth = {current[0]}..{current[-1]} vs the same months a year earlier, as a share "
            f"of each edition's human pageviews. Trend window {analysis.window[0]}.."
            f"{analysis.window[-1]}."
        ),
        "",
    ]
    for r in analysis.results:
        lines += [*_edition_lines(r), ""]
    for e in analysis.not_covered:
        lines.append(
            f"{e.label()}: NOT COVERED (no article on these concepts). Tell the user and ask "
            "whether to use a proxy; stop there. A request to compare this edition is not "
            "agreement to a proxy: add --proxy only after the user says yes in a new message."
        )
    if analysis.excluded:
        left = "; ".join(f"{k}: {', '.join(v)}" for k, v in analysis.excluded.items())
        lines.append(f"Left out to compare like with like (not in every edition): {left}")
    if not analysis.like_for_like:
        lines.append(
            "Warning: no concept is covered in every edition; editions are not like-for-like."
        )
    for d in analysis.differences:
        verdict = "clear difference" if d.clear else "no clear difference"
        lines.append(
            f"Comparison {d.leader} vs {d.other}: {d.growth_gap * 100:.1f} points apart "
            f"[90% range {d.interval.low * 100:+.1f} to {d.interval.high * 100:+.1f}] -> {verdict}"
        )
    lines += [f"Caveat (all editions): {c}" for c in analysis.caveats]
    lines += [
        "",
        f"Saved: {out_dir} (analysis.json, summary.txt, trend.png, growth.png)",
        f"Re-run: {data['rerun']}",
        (
            "Next: tell the user these verdicts with their confidence, reasons and caveats. Use "
            "only numbers shown here. For a shareable one-page PDF, write narrative.md in the run "
            f"folder, then run: {command} report --run {shlex.quote(str(out_dir))}"
        ),
    ]
    return "\n".join(lines)


def save(analysis: Analysis, out_root: Path, command: str) -> tuple[Path, str]:
    """Write the run dir and return it with the summary text."""
    rid = run_id(analysis, datetime.now(UTC))
    out_dir = (out_root / rid).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"trend": "trend.png", "growth": "growth.png"}
    data = to_json(analysis, rid, files, command)
    draw_trend(data, str(out_dir / files["trend"]), words("en"))
    draw_growth(data, str(out_dir / files["growth"]), words("en"))
    (out_dir / "analysis.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = format_summary(analysis, data, out_dir, command)
    # report checks the narrative's numbers against exactly what the model was shown (R3a)
    (out_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
    return out_dir, summary
