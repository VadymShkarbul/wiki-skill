"""The analyze step: baskets, metrics, verdicts, comparison (decisions D2-D5, M2-M7, T1-T5).

Interest is the share of an edition's human pageviews (views per million) that go to the
topic's articles. Growth compares each of the last P months (P = min(window, 12)) with the
same month a year earlier. Every verdict is computed here, with reasons written in words, so
the agent relays conclusions instead of deriving them.
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from wiki_interest import stats
from wiki_interest.editions import Catalog, Edition
from wiki_interest.errors import SkillError
from wiki_interest.mediawiki import JsonGetter
from wiki_interest.resolve import TitleRef, fetch_entities, make_concept, parse_ref, resolve_title
from wiki_interest.timeseries import (
    Daily,
    check_monthly_totals,
    fetch_article,
    fetch_edition_total,
    first_full_month,
    first_revision,
    last_full_month,
    month_end,
    month_range,
    month_start,
    request_end,
    shift_month,
)

MIN_MONTHS, MAX_MONTHS, DEFAULT_MONTHS = 3, 120, 24
INSUFFICIENT_VOLUME = 30
TINY_VOLUME = 100
AGREEING_SHARE = 0.75  # 9 of 12 months: one-sided sign test p ~ 0.07
SPIKE_SHIFT = 0.10  # despiked growth more than 10 points away means spike-driven
EDITION_SWING = 0.15
SEASONAL_PEAK = 1.2
RENAME_GAP_DAYS = 31
BOT_REVISION = ("2025-03", "2025-08")
AUTOMATED_CLASS_START = "2020-04"
PER_MILLION = 1e6
SORT_KEYS = ("growth", "size", "share")


# --- request --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConceptInfo:
    qid: str
    label: str


@dataclass
class ArticleUse:
    concept: ConceptInfo
    edition: Edition
    title: str
    proxy: bool
    created: date | None = None
    daily: Daily | None = None

    @property
    def first_day(self) -> date | None:
        return self.daily.first_viewed_day() if self.daily else None

    def renamed_hint(self) -> date | None:
        """If the title's pageview series starts long after the page's first revision, the
        page was probably renamed then; earlier views are counted under the old title (D4).

        Uses the series' first row, not its first nonzero day, so a quiet new article that
        goes unread for a while is not mistaken for a rename."""
        first = self.daily.start if self.daily else None
        if not (first and self.created):
            return None
        expected = max(self.created, date(2015, 7, 1))
        return first if (first - expected).days > RENAME_GAP_DAYS else None

    def first_month(self) -> str | None:
        if self.daily is None:
            return None
        starts = [d for d in (self.daily.start, self.created) if d]
        return first_full_month(max(starts)) if starts else None


def resolve_concepts(
    client: JsonGetter, catalog: Catalog, refs: list[str], editions: list[Edition]
) -> tuple[list[ConceptInfo], dict[str, dict[str, str]]]:
    """Return concepts and, per QID, the article title in each edition that has one."""
    qids: list[str] = []
    for text in refs:
        ref = parse_ref(text, catalog)
        if ref is None:
            raise SkillError(
                f"{text!r} is not a concept reference.",
                "Pass Wikidata IDs from `resolve` (e.g. --concepts Q1666254) or lang:Title. "
                "Run resolve first to find them.",
            )
        qid = ref if isinstance(ref, str) else resolve_title(client, ref)[0]
        if qid not in qids:
            qids.append(qid)
    languages = ["en", *(e.lang for e in editions)]
    entities = fetch_entities(client, qids, "labels|descriptions|sitelinks", languages)
    concepts, titles = [], {}
    for qid in qids:
        concept = make_concept(entities.get(qid, {}), catalog, editions, languages)
        if concept is None:
            raise SkillError(
                f"{qid} is not a topic with Wikipedia articles.",
                "Run resolve to find the right concept.",
            )
        concepts.append(ConceptInfo(qid, concept.label))
        titles[qid] = concept.titles
    return concepts, titles


def apply_proxies(  # noqa: PLR0913 - the proxy needs the full request context
    client: JsonGetter,
    catalog: Catalog,
    specs: list[str],
    concepts: list[ConceptInfo],
    titles: dict[str, dict[str, str]],
    *,
    editions: list[Edition],
) -> set[tuple[str, str]]:
    """Fill missing (concept, edition) cells from ``pl:Title`` or ``Q1=pl:Title`` specs (D3).
    Return the proxied cells."""
    proxied: set[tuple[str, str]] = set()
    for spec in specs:
        target, _, article = spec.partition("=") if "=" in spec.split(":")[0] else ("", "", spec)
        ref = parse_ref(article, catalog)
        if not isinstance(ref, TitleRef):
            raise SkillError(
                f"Proxy {spec!r} must look like pl:Title (or Q123=pl:Title).",
                "Use a proxy title listed by resolve, after the user agreed to it.",
            )
        code = ref.edition.code
        if code not in {e.code for e in editions}:
            raise SkillError(
                f"Proxy {spec!r} is for {code}, which is not in --editions.",
                f"Add {code} to --editions, or drop this --proxy.",
            )
        if target:
            owners = [c for c in concepts if c.qid == target.upper()]
        else:
            owners = [c for c in concepts if code not in titles[c.qid]][:1]
        if not owners or code in titles[owners[0].qid]:
            raise SkillError(
                f"Proxy {spec!r} does not fill a missing article: every concept already has "
                f"an article in {code}, or {target or 'the concept'} is not in --concepts.",
                "Drop this --proxy, or give its concept as Q123=pl:Title.",
            )
        _, canonical = resolve_title(client, ref)
        titles[owners[0].qid][code] = canonical
        proxied.add((owners[0].qid, code))
    return proxied


# --- per-edition result ---------------------------------------------------------------


@dataclass
class Verdict:
    direction: str  # growing | declining | no clear change | insufficient data
    confidence: str | None  # high | medium | low (None unless growing or declining)
    reasons: list[str]


@dataclass
class EditionResult:
    edition: Edition
    articles: list[ArticleUse]
    months: list[str] = field(default_factory=list)
    views: dict[str, float] = field(default_factory=dict)
    total: dict[str, float] = field(default_factory=dict)
    share: dict[str, float] = field(default_factory=dict)
    data_from: str | None = None
    growth: float = math.nan
    interval: stats.Interval = field(default_factory=lambda: stats.Interval(math.nan, math.nan))
    despiked_growth: float = math.nan
    spike_share: float = 0.0
    spike_days: list[tuple[str, int]] = field(default_factory=list)
    months_agreeing: int = 0
    pairs: int = 0
    trend_per_year: float = math.nan
    median_views: float = 0.0
    mean_share: float = 0.0
    edition_growth: float = math.nan
    seasonal_peak: tuple[str, float] | None = None
    verdict: Verdict = field(default_factory=lambda: Verdict("insufficient data", None, []))
    quadrant: str = ""
    caveats: list[str] = field(default_factory=list)
    total_gaps: list[tuple[str, float]] = field(default_factory=list)

    def arrays(self, current: list[str]) -> tuple[np.ndarray, np.ndarray]:
        cur = np.array([self.share[m] for m in current])
        prev = np.array([self.share[shift_month(m, -12)] for m in current])
        return cur, prev


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _decide(result: EditionResult, required_pairs: int) -> Verdict:
    """Direction from the 90% interval; confidence from High minus one level per issue (T3)."""
    if no_data := [a.title for a in result.articles if a.daily is None]:
        titles = ", ".join(repr(t) for t in no_data)
        return Verdict("insufficient data", None, [f"Wikimedia has no pageview data for {titles}"])
    if result.pairs < required_pairs:
        return Verdict(
            "insufficient data",
            None,
            [
                (
                    f"pageview data under this title starts {result.data_from}; a year-over-year "
                    f"comparison of {required_pairs} months needs data from 12 months earlier"
                )
            ],
        )
    if result.median_views < INSUFFICIENT_VOLUME:
        return Verdict(
            "insufficient data",
            None,
            [f"only {result.median_views:.0f} views/month, below the {INSUFFICIENT_VOLUME} floor"],
        )
    ci = result.interval
    if not ci.excludes_zero():
        return Verdict(
            "no clear change",
            None,
            [f"the 90% range {_pct(ci.low)} to {_pct(ci.high)} includes zero"],
        )
    direction = "growing" if ci.low > 0 else "declining"
    word = "above" if direction == "growing" else "below"
    reasons, issues = [], 0
    agree_needed = math.ceil(AGREEING_SHARE * result.pairs)
    agree = f"{result.months_agreeing} of {result.pairs} months {word} the same month last year"
    if result.months_agreeing >= agree_needed:
        reasons.append(f"consistent: {agree}")
    else:
        issues += 1
        reasons.append(f"inconsistent: only {agree} (needs {agree_needed})")
    shift = result.despiked_growth - result.growth
    flipped = (result.despiked_growth > 0) != (result.growth > 0)
    if abs(shift) > SPIKE_SHIFT or flipped:
        issues += 1
        reasons.append(
            f"spike-driven: without {len(result.spike_days)} spike days growth is "
            f"{_pct(result.despiked_growth)}"
        )
    if result.median_views < TINY_VOLUME:
        issues += 1
        reasons.append(f"tiny volume: {result.median_views:.0f} views/month")
    confidence = ("high", "medium", "low")[min(issues, 2)]
    return Verdict(direction, confidence, reasons)


def _seasonal_peak(share: dict[str, float], last: str) -> tuple[str, float] | None:
    """Calendar month that is highest in each of the last two years, if clearly high (M4)."""
    months = month_range(shift_month(last, -23), last)
    if any(m not in share for m in months):
        return None
    ratios: dict[str, list[float]] = {}
    for block in (months[:12], months[12:]):
        mean = np.mean([share[m] for m in block])
        if mean <= 0:
            return None
        for m in block:
            ratios.setdefault(m[5:], []).append(share[m] / mean)
    peak = max(ratios, key=lambda k: min(ratios[k]))
    lift = float(min(ratios[peak]))
    return (peak, lift) if lift >= SEASONAL_PEAK else None


@dataclass
class _Basket:
    views: dict[str, float]  # monthly views over the full history
    cleaned: dict[str, float]  # monthly views with spike days replaced, compared span only
    removed: float  # views removed by despiking in the compared span
    spike_days: list[tuple[str, int]]


def _accumulate(articles: list[ArticleUse], span_first: date, span_last: date) -> _Basket:
    """Sum the basket's articles, and despike each over the two compared years (T5)."""
    basket = _Basket({}, {}, 0.0, [])
    for article in articles:
        if article.daily is None:
            continue
        for m, v in article.daily.monthly().items():
            basket.views[m] = basket.views.get(m, 0.0) + v
        first_day = max(span_first, article.daily.start)
        days = article.daily.days_in(first_day, span_last)
        spikes = stats.despike(days)
        basket.removed += float((days - spikes.cleaned).sum())
        for offset, value in enumerate(spikes.cleaned):
            m = (first_day + timedelta(days=offset)).isoformat()[:7]
            basket.cleaned[m] = basket.cleaned.get(m, 0.0) + float(value)
        basket.spike_days += [
            ((first_day + timedelta(days=int(i))).isoformat(), int(days[i])) for i in spikes.days
        ]
    return basket


def _measure(
    result: EditionResult, window: list[str], current: list[str], first_needed: str
) -> None:
    """Fill the metrics of one edition's basket (M2, M3, T2, T3, T5)."""
    starts = [a.first_month() for a in result.articles]
    result.data_from = max(s for s in starts if s) if starts and all(starts) else None
    total = result.total
    basket = _accumulate(
        result.articles, month_start(shift_month(current[0], -12)), month_end(current[-1])
    )
    views, cleaned, removed, spike_days = (
        basket.views,
        basket.cleaned,
        basket.removed,
        basket.spike_days,
    )
    result.months = [m for m in month_range(first_needed, window[-1]) if m in total]
    result.views = {m: views.get(m, 0.0) for m in result.months}
    result.share = {m: result.views[m] / total[m] * PER_MILLION for m in result.months}
    if result.data_from is None:
        return
    result.pairs = sum(1 for m in current if shift_month(m, -12) >= result.data_from)
    result.median_views = float(np.median([result.views[m] for m in current]))
    result.mean_share = float(np.mean([result.share[m] for m in current]))
    if all(shift_month(m, -12) in total for m in current):
        result.edition_growth = stats.yoy_growth(
            np.array([total[m] for m in current]),
            np.array([total[shift_month(m, -12)] for m in current]),
        )
    if result.pairs < len(current):
        return
    cur, prev = result.arrays(current)
    result.growth = stats.yoy_growth(cur, prev)
    result.interval = stats.bootstrap_growth(cur, prev)
    if result.growth > 0:
        result.months_agreeing = stats.months_up(cur, prev)
    else:
        result.months_agreeing = stats.months_down(cur, prev)

    def cleaned_share(m: str) -> float:
        return cleaned.get(m, 0.0) / total[m]

    result.despiked_growth = stats.yoy_growth(
        np.array([cleaned_share(m) for m in current]),
        np.array([cleaned_share(shift_month(m, -12)) for m in current]),
    )
    compared = sum(result.views[m] + result.views[shift_month(m, -12)] for m in current)
    result.spike_share = removed / compared if compared else 0.0
    result.spike_days = sorted(spike_days, key=lambda day: -day[1])
    trend = [result.share[m] for m in window if m >= result.data_from]
    result.trend_per_year = stats.theil_sen_annual(np.array(trend))
    if len(window) >= 24:  # noqa: PLR2004 - two full years are needed to name a seasonal peak
        result.seasonal_peak = _seasonal_peak(result.share, window[-1])


# --- caveats, comparison, quadrant ----------------------------------------------------


def _overlaps(months: list[str], first: str, last: str) -> bool:
    return any(first <= m <= last for m in months)


def edition_caveats(result: EditionResult, compared: list[str]) -> list[str]:
    notes = []
    for a in result.articles:
        if a.proxy:
            notes.append(
                f"uses proxy article {a.title!r} in place of {a.concept.label} ({a.concept.qid})"
            )
        if a.daily is None:
            notes.append(f"no pageview data for {a.title!r}")
            continue
        renamed = a.renamed_hint()
        if renamed:
            notes.append(
                f"{a.title!r} was probably renamed around {renamed}: earlier views are counted "
                "under its old title and are not included"
            )
        elif a.created and a.created.isoformat()[:7] >= compared[0]:
            notes.append(f"{a.title!r} was created on {a.created}, inside the compared period")
    swing = result.edition_growth
    if math.isfinite(swing) and abs(swing) >= EDITION_SWING:
        notes.append(
            f"all of {result.edition.code} Wikipedia changed {_pct(swing)} year over year; "
            "share-of-edition figures remove this effect"
        )
    return notes


def global_caveats(
    compared: list[str], window: list[str], results: list[EditionResult]
) -> list[str]:
    months = sorted(set(compared) | set(window))
    notes = []
    gaps = [g for r in results for g in r.total_gaps]
    if gaps:
        gap_months = ", ".join(sorted({m for m, _ in gaps}))
        worst = max(abs(g) for _, g in gaps)
        notes.append(
            f"Wikimedia's daily and monthly edition totals differ slightly in {gap_months} "
            f"(at most {worst * 100:.2f}%); figures here use the daily data"
        )
    if _overlaps(months, *BOT_REVISION):
        notes.append(
            "Wikimedia changed bot detection in 2025 and reclassified Mar-Aug 2025 traffic; "
            "share-of-edition figures absorb part of this, since totals were reclassified too"
        )
    if months[0] < AUTOMATED_CLASS_START:
        notes.append(
            "before 2020-04 Wikimedia did not separate automated traffic, so earlier 'human' "
            "views include some bots"
        )
    return notes


def assign_quadrants(results: list[EditionResult]) -> None:
    """Size relative to the compared editions' median; growth from the verdict (M6, T4)."""
    sized = [r for r in results if r.verdict.direction != "insufficient data"]
    if len(sized) < 2:  # noqa: PLR2004 - a quadrant needs something to compare with
        return
    median = float(np.median([r.median_views for r in sized]))
    for r in sized:
        size = "large" if r.median_views >= median else "small"
        r.quadrant = {
            "growing": f"{size} & growing",
            "no clear change": f"{size} & flat",
            "declining": "declining",
        }[r.verdict.direction]


@dataclass
class Difference:
    leader: str
    other: str
    growth_gap: float
    interval: stats.Interval

    @property
    def clear(self) -> bool:
        return self.interval.excludes_zero()


def compare(results: list[EditionResult], current: list[str]) -> list[Difference]:
    """Each edition against the fastest-growing one, on the same calendar months (T2)."""
    ranked = [r for r in results if math.isfinite(r.growth)]
    if len(ranked) < 2:  # noqa: PLR2004 - a comparison needs two editions
        return []
    ranked.sort(key=lambda r: -r.growth)
    leader, *others = ranked
    lead_cur, lead_prev = leader.arrays(current)
    diffs = []
    for other in others:
        cur, prev = other.arrays(current)
        diffs.append(
            Difference(
                leader.edition.code,
                other.edition.code,
                leader.growth - other.growth,
                stats.bootstrap_difference(lead_cur, lead_prev, cur, prev),
            )
        )
    return diffs


def sort_results(results: list[EditionResult], key: str) -> list[EditionResult]:
    def value(r: EditionResult) -> float:
        if key == "size":
            return r.median_views
        if key == "share":
            return r.mean_share
        return r.growth if math.isfinite(r.growth) else -math.inf

    return sorted(results, key=value, reverse=True)


# --- orchestration --------------------------------------------------------------------


@dataclass
class Analysis:
    concepts: list[ConceptInfo]
    editions: list[Edition]
    months: int
    sort: str
    proxies: list[str]
    window: list[str]
    current: list[str]
    data_through: date
    results: list[EditionResult]
    not_covered: list[Edition]
    excluded: dict[str, list[str]]
    like_for_like: bool
    differences: list[Difference]
    caveats: list[str]


def run_analysis(  # noqa: PLR0913 - mirrors the CLI flags one to one
    client: JsonGetter,
    catalog: Catalog,
    concept_refs: list[str],
    editions: list[Edition],
    *,
    months: int = DEFAULT_MONTHS,
    proxies: list[str] | None = None,
    sort: str = "growth",
    today: date | None = None,
) -> Analysis:
    if not MIN_MONTHS <= months <= MAX_MONTHS:
        raise SkillError(
            f"--months {months} is out of range.",
            f"Use a window between {MIN_MONTHS} and {MAX_MONTHS} months (default 24).",
        )
    concepts, titles = resolve_concepts(client, catalog, concept_refs, editions)
    proxied = apply_proxies(client, catalog, proxies or [], concepts, titles, editions=editions)

    covered = [e for e in editions if any(e.code in titles[c.qid] for c in concepts)]
    not_covered = [e for e in editions if e not in covered]
    if not covered:
        names = ", ".join(e.label() for e in editions)
        raise SkillError(
            f"None of the concepts has an article in {names}.",
            "Tell the user. Run resolve to see proxies, and add --proxy only if the user agrees.",
        )
    common = [c for c in concepts if all(e.code in titles[c.qid] for e in covered)]
    like_for_like = bool(common)
    excluded: dict[str, list[str]] = {}
    basket: dict[str, list[ConceptInfo]] = {}
    for e in covered:
        chosen = common or [c for c in concepts if e.code in titles[c.qid]]
        basket[e.code] = chosen
        left_out = [c.qid for c in concepts if c not in chosen and e.code in titles[c.qid]]
        if left_out:
            excluded[e.code] = left_out

    end = request_end(today)
    totals = {e.code: fetch_edition_total(client, e, end) for e in covered}
    data_through = min(t.end for t in totals.values())
    last = last_full_month(data_through)
    window = month_range(shift_month(last, -(months - 1)), last)
    current = window[-min(months, 12) :]
    compared = [shift_month(current[0], -12), *current]
    first_needed = min(shift_month(window[0], -11), shift_month(current[0], -12))

    results = []
    for e in covered:
        gaps = check_monthly_totals(client, e, totals[e.code], month_range(compared[0], last))
        articles = []
        for concept in basket[e.code]:
            title = titles[concept.qid][e.code]
            articles.append(
                ArticleUse(
                    concept,
                    e,
                    title,
                    (concept.qid, e.code) in proxied,
                    first_revision(client, e, title),
                    fetch_article(client, e, title, end),
                )
            )
        result = EditionResult(e, articles, total=totals[e.code].monthly(), total_gaps=gaps)
        _measure(result, window, current, first_needed)
        result.verdict = _decide(result, len(current))
        result.caveats = edition_caveats(result, compared)
        results.append(result)
    assign_quadrants(results)
    return Analysis(
        concepts=concepts,
        editions=editions,
        months=months,
        sort=sort,
        proxies=proxies or [],
        window=window,
        current=current,
        data_through=data_through,
        results=sort_results(results, sort),
        not_covered=not_covered,
        excluded=excluded,
        like_for_like=like_for_like,
        differences=compare(results, current),
        caveats=global_caveats(compared, window, results),
    )
