# How the numbers are computed

Read this when the user asks how a result was reached or how far to trust it. Everything here
is done by the scripts; you only need it to explain the results.

## Data

- **Source:** Wikimedia Pageviews API, human traffic only (Wikimedia's `user` agent class),
  desktop and mobile combined. Data starts on 2015-07-01 and runs until yesterday.
- **Same concept in every language:** each topic is a Wikidata item, which links to the
  article on that concept in each edition. This is what makes "Polish vs Czech" a comparison
  of the same thing.
- **Full calendar months only.** A partial current month would make the latest month look
  like a collapse.

## Interest

**Share of edition** is the topic's views per million of all human views in that edition.
Edition size and edition-wide swings cancel out: Ukrainian Wikipedia's total traffic rose
about 50% from 2021 to 2024 and has fallen since, and raw views would show that swing as if it
were a change in the topic. Raw views per month are shown next to share, because audience size
matters too.

When several concepts form one topic, their shares are added up. Only concepts that have an
article in every compared edition are used, so all editions are measured on the same basis.

## Growth

Growth compares each of the last 12 full months with the same month one year earlier, using
share of edition. A January is always compared with a January, so seasonality cancels out.
With `--months` under 12, only the months in the window are compared, each with the same
month a year earlier. The window otherwise only sets how much history the trend chart shows.

## The 90% range

The 12 month pairs are resampled 2,000 times with a fixed seed, so the same data always gives
the same numbers. The middle 90% of the results is the range.

- The range entirely above 0 means **growing**; entirely below 0 means **declining**.
- A range that includes 0 means **no clear change**. The data can't tell a real trend from
  noise, so don't call it a decline even when the central number is negative.
- With only 12 pairs, the range may be slightly too narrow.

## Confidence (for growing or declining)

Confidence starts at high and drops one level for each issue:

| Issue | Meaning |
|---|---|
| Inconsistent | Fewer than 9 of 12 months moved in the verdict's direction. |
| Spike-driven | Without spike days, growth differs by more than 10 points or changes sign. A spike day is far above the surrounding four weeks, e.g. after a news story. |
| Tiny volume | Under 100 views a month: one school class or one bot could create the pattern. |

**Insufficient data** means that edition's articles have less than a year of history before
the compared period, or under 30 views a month.

## Comparing editions and segments

- Each edition is compared with the fastest-growing one on the same calendar months. If the
  90% range of the difference includes 0, there is **no clear difference**.
- Segments: an edition is **large** when its views per month are at or above the median of the
  compared editions, otherwise **small**. The label combines size and verdict ("large &
  growing", "small & flat"). Declining editions are just "declining".

## Caveats you may see

| Caveat | Meaning |
|---|---|
| Proxy article | A broader article, chosen with the user, stands in where an edition has none. It measures something related, not the same concept. |
| Probably renamed | Views under the current title start long after the page was created. Earlier views are under the old title and not counted. |
| Created inside the compared period | The article is new, so early months can look like growth. |
| Edition changed X% | The whole edition's traffic moved a lot. Share already removes this; it is context. |
| 2025 bot detection change | Wikimedia reclassified some 2025 traffic as bots. Share absorbs part of this. |
| Daily vs monthly totals differ | Wikimedia's own two totals differ slightly (under 1%) in a few months. The daily data is used. |

## Limits

- Attention on Wikipedia is not demand, willingness to pay, or market size.
- Readers also get answers from search engines and AI assistants, so Wikipedia views are
  declining in many editions. Share of edition corrects for edition-wide change, but not for
  topic-specific shifts to other sources.
- Only articles' current titles are counted. Views through redirects are not included.
