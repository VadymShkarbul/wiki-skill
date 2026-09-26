# Data sources: research notes

Probed live on 2026-09-26 with `curl` plus official docs. "Confirmed" means seen in a live
response. "Unconfirmed" means not verified yet, with where I looked.

## Endpoints we need

| Purpose | Endpoint | Notes |
|---|---|---|
| Views of one article | `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{title}/{daily\|monthly}/{YYYYMMDD}/{YYYYMMDD}` | One request returns the whole date range. |
| Total views of an edition (normalization) | `.../pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}` | Same shape, with no title. |
| Most-viewed articles (discovery) | `.../pageviews/top/{project}/{access}/{YYYY}/{MM}/{DD\|all-days}` | Returns 1000 items, including the main page and `Special:` pages. |
| Topic → same article in every language | Wikidata `wbgetentities&sites=enwiki&titles=…&props=sitelinks` | Sitelinks give the exact title per edition. |
| Free text → Wikidata item | Wikidata `wbsearchentities&search=…` | Results are ambiguous: "astronomy" also matches a journal and a song. |
| Redirects to an article | MediaWiki `prop=redirects` | enwiki "Intermittent fasting" has about 25 redirects. |

Parameter values: `access` = all-access / desktop / mobile-web / mobile-app;
`agent` = user / spider / automated / all-agents. Data licence: CC0.

## Confirmed pitfalls (these drive the design)

1. **An edition may have no article on the topic.** plwiki has no sitelink for
   intermittent fasting (Q1666254 links only cs, en and uk). The closest is "Głodówka lecznicza"
   (therapeutic fasting), which is a different concept. The spec's first example hits this.
2. **Monthly granularity silently includes partial months.** `end=20240401` returned April
   as 2,358 views, which is one day, while full months were about 70k. Naive growth math breaks.
3. **Monthly requests whose end date falls inside the first month return HTTP 400.** For example
   `.../monthly/2024010100/2024012800`. Found during the Haiku probe; the end date must reach the month's last day.
4. **The start date is silently clamped to 2015-07-01.** No error is returned.
5. **A 404 is ambiguous.** "No such article" and "no data" return the same message.
6. **Daily series have gaps.** For Aug 1 to Sep 25 (56 days), 54 rows came back and some days showed 0.
   The series has to be reindexed onto a full calendar.
7. **Data lags by about one day.** The latest daily row was yesterday.
8. **Redirects are counted separately.** Jan 2024: "UK" had 5,657 views and "United_Kingdom" had 815,550.
   A renamed article splits its history across titles.
9. **Whole editions trend strongly, so raw views mislead.** January user views:

   | Edition | 2019 | 2022 | 2024 | 2025 | 2026 |
   |---|---|---|---|---|---|
   | uk | 56.6M | 72.6M | 115.3M | 94.1M | 60.5M |
   | pl | 292M | 282M | 258M | 252M | 204M |
   | cs | 80M | 91M | 86M | 83M | 67M |
   | en | 8.21B | 7.57B | 8.68B | 8.08B | 7.23B |

   Normalization matters. Example: ukwiki "Астрономія" in January, as views per million
   edition views, fell 47.2 (2021) → 33.0 → 19.4 → 32.1 → 16.6 → 7.4 (2026).
10. **Single months are noisy and seasonal.** enwiki "Intermittent fasting" had 74k views in Jan 2024
   and 44k in Feb 2024, probably a New Year's-resolution effect. We need rolling or
   same-month comparisons.
11. **The meaning of "user" traffic changes over time.** The `automated` class only exists from
    2020-04. ukwiki Jan 2026: user 60.5M, spider 37.4M, automated 25.9M. Wikimedia
    updated bot detection in 2025, reclassified Mar–Aug 2025, and reports about 8% lower
    human views year over year ([WMF, 2025-10-17](https://wikimediafoundation.org/news/2025/10/17/new-user-trends-on-wikipedia/)).
    Trends that cross 2020-04 or 2025 carry a methodology-change caveat.

## Access rules

- **User-Agent is required** in the form `<client>/<version> (<contact>) <lib>/<version>`.
  Clients without one may be blocked
  ([UA policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)).
- **Rate limits:** 10 requests/min with no identification, 200/min with a compliant UA; HTTP 429
  with `Retry-After`, and back off at least 5 s when that header is missing
  ([rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)). The docs advise sending
  requests one at a time.
- **Responses carry `cache-control: max-age=14400` (4 h).** Past data doesn't change except
  for rare reclassification, so a local cache is safe and cheap.
- **Bulk data:** dumps at https://dumps.wikimedia.org/other/analytics/, for the roadmap.

## Unconfirmed

- ~~Whether missing daily rows mean 0 views.~~ **Resolved 2026-09-26:** for 7 articles over
  36 months, the sum of daily rows equals the monthly endpoint exactly, including cs
  "Přerušovaný půst" with 2 missing days. So a missing day means 0 views.
- Whether the rate limits page applies to the pageviews REST endpoints: that page speaks of
  "Action API and REST APIs" in general. Plan for 200 requests/min.
- The official page-views reference didn't render through my fetcher. The endpoint shapes
  above come from live responses instead.
