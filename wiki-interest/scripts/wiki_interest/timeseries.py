"""Pageview time series: fetching, calendar months, and data checks (decisions M1, M7, I4, T5).

Every series is fetched once as the full daily history since 2015-07-01 (one request, cached
for a day), so changing the window or re-running costs no requests. Only human traffic
(agent=user) on all access methods is used, in both numerator and denominator.
"""

import urllib.parse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np

from wiki_interest.editions import Edition
from wiki_interest.errors import SkillError
from wiki_interest.http_client import NotFoundError
from wiki_interest.mediawiki import WEEK, JsonGetter, action_api

PAGEVIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
DATA_START = date(2015, 7, 1)
DAY_TTL = 24 * 3600
ACCESS, AGENT = "all-access", "user"
TOTALS_TOLERANCE = 0.01  # daily vs monthly totals: small gaps exist after reprocessing (T5a)


# --- months ---------------------------------------------------------------------------


def month_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def shift_month(month: str, delta: int) -> str:
    year, mon = map(int, month.split("-"))
    index = year * 12 + mon - 1 + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_range(first: str, last: str) -> list[str]:
    months, current = [], first
    while current <= last:
        months.append(current)
        current = shift_month(current, 1)
    return months


def month_start(month: str) -> date:
    year, mon = map(int, month.split("-"))
    return date(year, mon, 1)


def month_end(month: str) -> date:
    return month_start(shift_month(month, 1)) - timedelta(days=1)


def last_full_month(data_through: date) -> str:
    """The latest month whose every day is in the data."""
    month = month_of(data_through)
    return month if month_end(month) == data_through else shift_month(month, -1)


def first_full_month(first_day: date) -> str:
    """The first month that starts on or after ``first_day`` (a partial first month is dropped)."""
    month = month_of(first_day)
    return month if first_day.day == 1 else shift_month(month, 1)


# --- series ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Daily:
    """Contiguous daily views from ``start``; days missing in the API are 0 (verified)."""

    start: date
    views: np.ndarray

    @property
    def end(self) -> date:
        return self.start + timedelta(days=len(self.views) - 1)

    def first_viewed_day(self) -> date | None:
        nonzero = np.flatnonzero(self.views)
        return self.start + timedelta(days=int(nonzero[0])) if nonzero.size else None

    def monthly(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for offset, views in enumerate(self.views):
            key = month_of(self.start + timedelta(days=offset))
            totals[key] = totals.get(key, 0.0) + float(views)
        return totals

    def days_in(self, first: date, last: date) -> np.ndarray:
        lo = max((first - self.start).days, 0)
        hi = min((last - self.start).days + 1, len(self.views))
        return self.views[lo:hi] if hi > lo else np.zeros(0)


def _day(timestamp: str) -> date:
    return date(int(timestamp[:4]), int(timestamp[4:6]), int(timestamp[6:8]))


def _parse_items(items: list[dict]) -> Daily | None:
    if not items:
        return None
    days = {_day(i["timestamp"]): i["views"] for i in items}
    start, end = min(days), max(days)
    views = np.zeros((end - start).days + 1)
    for day, count in days.items():
        views[(day - start).days] = count
    return Daily(start, views)


def request_end(today: date | None = None) -> date:
    return (today or datetime.now(UTC).date()) - timedelta(days=1)


def _stamp(day: date) -> str:
    return day.strftime("%Y%m%d") + "00"


def fetch_article(client: JsonGetter, edition: Edition, title: str, end: date) -> Daily | None:
    """Daily views of one article, or None when the API has no data for the title."""
    encoded = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = (
        f"{PAGEVIEWS}/per-article/{edition.project}/{ACCESS}/{AGENT}/{encoded}/daily/"
        f"{_stamp(DATA_START)}/{_stamp(end)}"
    )
    try:
        return _parse_items(client.get_json(url, ttl=DAY_TTL).get("items", []))
    except NotFoundError:
        return None


def fetch_edition_total(client: JsonGetter, edition: Edition, end: date) -> Daily:
    url = (
        f"{PAGEVIEWS}/aggregate/{edition.project}/{ACCESS}/{AGENT}/daily/"
        f"{_stamp(DATA_START)}/{_stamp(end)}"
    )
    try:
        series = _parse_items(client.get_json(url, ttl=DAY_TTL).get("items", []))
    except NotFoundError:
        series = None
    if series is None:
        raise SkillError(
            f"Wikimedia has no pageview totals for {edition.label()} Wikipedia.",
            "Tell the user this edition cannot be analyzed and re-run without it.",
        )
    return series


def check_monthly_totals(
    client: JsonGetter, edition: Edition, daily_total: Daily, months: list[str]
) -> list[tuple[str, float]]:
    """Built-in check (T5a): summed daily totals must match Wikimedia's own monthly totals.

    Wikimedia's two aggregates differ slightly in reprocessed months (e.g. 2025-03, -0.12% on
    every edition checked). Gaps up to 1% are returned so they can be shown as a caveat; larger
    gaps stop the run. Analyses always use the daily sums.
    """
    url = (
        f"{PAGEVIEWS}/aggregate/{edition.project}/{ACCESS}/{AGENT}/monthly/"
        f"{_stamp(month_start(months[0]))}/{_stamp(month_end(months[-1]))}"
    )
    official = {
        f"{i['timestamp'][:4]}-{i['timestamp'][4:6]}": i["views"]
        for i in client.get_json(url, ttl=DAY_TTL).get("items", [])
    }
    ours = daily_total.monthly()
    gaps = []
    for month in months:
        if month not in official or not official[month]:
            continue
        gap = ours.get(month, 0.0) / official[month] - 1
        if abs(gap) > TOTALS_TOLERANCE:
            raise SkillError(
                f"Wikimedia data is inconsistent for {edition.label()} {month}: daily totals "
                f"sum to {ours.get(month, 0):.0f} but the monthly total is {official[month]}.",
                "Re-run the same command later (Wikimedia may be reprocessing data). If it "
                "persists, tell the user.",
            )
        if gap:
            gaps.append((month, gap))
    return gaps


def first_revision(client: JsonGetter, edition: Edition, title: str) -> date | None:
    """Date of the page's first revision (its creation, or earlier history moved with it)."""
    data = action_api(
        client,
        edition.api,
        {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvlimit": "1",
            "rvdir": "newer",
            "rvprop": "timestamp",
        },
        ttl=WEEK,
    )
    revisions = data["query"]["pages"][0].get("revisions")
    if not revisions:
        return None
    return date.fromisoformat(revisions[0]["timestamp"][:10])
