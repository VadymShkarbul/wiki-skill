# Roadmap: from basic questions to larger research

The first version answers one kind of question well: how interest in a few chosen concepts moves
across a few chosen editions, and how far to trust it. This roadmap says how to grow it, in the
order the evidence suggests. Every step keeps the same rule that got v1 to 10/10 on Haiku: code
does the thinking, the model relays, and every change is gated by the eval suite
(`evals/run.py`) before it ships.

## How each change is made

1. Add eval cases that express the new capability, including one near-miss the skill should
   refuse or ask about. Watch them fail.
2. Change code first and SKILL.md second. Put decision-critical cues in the command output,
   where a small model reads them (lesson from the evals, decision I3a).
3. Re-run the suite on the cheapest target model (N=3) and log the result in
   `evals/iteration-log.md`. A change that drops any case below 3/3 doesn't ship.

## Stage 1: harden what exists (small, high value)

| Item | Why | Decision it extends |
|---|---|---|
| Portability runs via OpenCode + OpenRouter (Gemini Flash, DeepSeek, Qwen, free tiers) | Show the skill isn't tied to Claude; find wording that only Claude follows. | E1 |
| Grow the eval set to about 30 cases (more languages, topics, and failure modes) plus an LLM judge for answer quality | 10 cases prove the core flows, not the long tail. The judge covers what regexes can't, e.g. whether the recommendation follows from the verdicts. | E2, E3 |
| Check that direction words in the narrative ("growing") match each edition's verdict | The last gap in "verify conclusions": numbers are checked, words aren't. | R3 |
| Translate caveats, reasons, and edition names | A Ukrainian report still has English caveat sentences. | R4 |
| Noto fonts for non-Latin/Cyrillic/Greek scripts | Hindi, Japanese, Arabic editions can be analyzed but not rendered in the PDF. | R4 |
| Optimize the description with skill-creator's `run_loop` | Measured triggering accuracy instead of hand-tuned wording. | S5 |

## Stage 2: more complex research

**Stitch history across renames and redirects (D4).** Today a renamed article is flagged and its
history trimmed. Next: read the move log, then add the old title's views before the rename and
redirect views after it. Evidence that this matters: after one rename, the old title still drew
5.7k views a month.

**Topic discovery (`discover` command).** Founders often ask "what should we build?", not "is X
growing?". The pageviews `top` endpoint gives the 1,000 most-read articles per edition and day.
Mapping them to Wikidata items and their classes (P31/P279) lets the skill rank rising topics
within a domain (e.g. "health", "learning") per edition. The output stays the same shape: a
short, relay-ready list, each item analyzable with `analyze`.

**Topic baskets from the Wikidata graph (D2 roadmap).** Build a broad topic's basket from
subclasses and parts of a concept, e.g. astronomy -> planets, telescopes, constellations.
Keep the like-for-like rule (only concepts covered in every compared edition) and show the
basket before analyzing, so the user approves the definition as with proxies.

**Portfolio questions.** "Which of these 12 course ideas?" is `analyze` over many concept sets
with one ranking table. Add a `--spec file.json` input for batches (I2 chose flags for
single runs), and keep the output a ranked summary plus one JSON per topic.

**Richer statistics, only where evals show a need.** A daily block bootstrap for tighter,
honest intervals (T2). A mobile/desktop split (M7), which matters for app founders. User-weighted
ranking criteria (M6). Each needs an explanation a founder can follow in one sentence, or it
stays out.

**Validation beyond Wikipedia.** Pageviews are attention, not demand. The natural next signals
are search interest, app-store keyword data, and the founder's own funnel. The skill should
state which signal it lacks rather than pretend to cover it.

## Stage 3: larger data volumes

The API allows about 200 requests a minute. v1 needs one request per article per edition, which
is fine for a few dozen series. Research over thousands of articles needs a different data layer:

| Scale | Approach |
|---|---|
| Up to ~500 series per run | Keep the API. Add a token bucket and parallel fetches under the limit, incremental updates (fetch only days after the cached end), and a SQLite store instead of one JSON file per response. |
| Thousands of articles or all editions | Switch to Wikimedia's monthly `pageview_complete` dumps (https://dumps.wikimedia.org/other/pageview_complete/). Convert them once to Parquet partitioned by edition and month, and query them with DuckDB. Reports then read aggregates, not raw rows. |
| Reproducible research | Pin `data_through` and store the aggregate snapshot with the run, so a report can be rebuilt byte for byte months later. |

The command interface doesn't change with the data layer. `resolve`, `analyze`, and `report`
keep their output contract, so SKILL.md and the evals stay valid while the backend grows.

## What not to build

- **Forecasts.** Two years of monthly data and a 90% range that often includes zero don't
  support honest forecasts. Saying "no clear change" is the feature.
- **Explaining spikes automatically.** Linking a spike to news needs search and judgment. The
  skill leaves spike causes to the user, or to a separate, clearly labeled lookup.
- **One opaque "opportunity score".** The spec says users bring their own criteria. Transparent
  dimensions plus `--user-numbers` let the report state them (M6, R3a).
