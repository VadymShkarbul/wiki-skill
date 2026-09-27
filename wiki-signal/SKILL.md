---
name: wiki-signal
description: >-
  Measures how interest in a topic changes across Wikipedia language editions, using Wikimedia
  pageview data, and turns it into verdicts with confidence, charts, and a one-page PDF report.
  Use it whenever someone wants to know whether interest in a topic is growing or declining, how
  much that trend can be trusted, or which language audiences or markets look most promising,
  for example a founder choosing the next course, topic, or localization language for an app,
  even if they don't mention Wikipedia or pageviews. Also use it for comparing a topic across
  languages or countries (e.g. Polish vs Czech) and for shareable interest or demand-signal
  reports. Not for editing Wikipedia, looking up facts in articles, or analyzing a website's
  own traffic.
license: MIT
compatibility: Needs uv (https://docs.astral.sh/uv/) and internet access to Wikimedia APIs.
---

# Wikipedia interest

Three commands do all the data work: `resolve` finds the topic's article in each language
edition, `analyze` computes the verdicts and charts, and `report` makes the one-page PDF. Your
job is to pick the right concept with the user, run the commands, and pass the results on
faithfully.

Pageviews measure attention on Wikipedia, not demand or willingness to pay. Present every
result as a signal of what to validate next, never as proof that people will buy.

## Running commands

Run every command from any directory, exactly like this, where `SKILL_DIR` is the absolute
path of the folder that contains this SKILL.md:

```
uv run SKILL_DIR/scripts/wiki.py <command> [options]
```

Don't `cd` first. The first run downloads dependencies (a few seconds); later runs are fast
and reuse cached data, so re-running with different options is cheap.

If a command fails, it prints `Error:` and `Next:`. Tell the user the error and do what `Next:`
says. Don't write your own code, `curl`, or scripts to fetch or compute the data instead: the
commands handle Wikimedia's data traps (partial months, bot traffic, renamed articles), and
improvised code gets them wrong. If `uv` is missing, see [references/setup.md](references/setup.md).

## Workflow

### 1. Find the concept: `resolve`

```
uv run SKILL_DIR/scripts/wiki.py resolve "intermittent fasting" --editions pl,cs
```

- `--editions` takes Wikipedia codes (`pl`, `cs`, `uk`, `de`) or English language names
  (`Polish`). Check the names it prints: `cz` is not Czech (use `cs`), `ua` is not Ukrainian
  (use `uk`).
- If the topic is written in another language, add `--search-lang` with that language's code,
  e.g. `--search-lang uk`.
- It lists candidate concepts with their Wikidata ID (like `Q1666254`) and the article title
  in each edition. Pick the one that matches what the user means. If more than one could fit
  (e.g. "Mercury": planet, element, god), ask the user.
- If nothing fits, re-run with the concept's encyclopedic name: "English language" rather than
  "learning English".
- **NOT COVERED** means that edition has no article on the concept. The output may list
  proxies: articles on a broader concept, e.g. "Post" (fasting in general) for intermittent
  fasting. A proxy measures a different thing, so it's the user's call:
  1. Run `analyze` now **without** `--proxy`, so the user gets the covered editions' results.
  2. Say which edition is not covered, name the proxy and what it really measures, and ask
     whether to add it.
  3. Add `--proxy` only in a later run, after the user says yes. Asking to compare an
     edition is not agreement to a proxy for it.

### 2. Analyze: `analyze`

```
uv run SKILL_DIR/scripts/wiki.py analyze --concepts Q1666254 --editions pl,cs
```

- `--months` sets the trend window (default 24, e.g. 36 for "the last three years"). Growth
  always compares the last 12 full months with the same months a year earlier.
- `--proxy pl:Post` fills a not-covered edition, only after the user agreed to that proxy.
- Several concepts (`--concepts Q1 Q2 Q3`) are measured together as one broad topic. Use this
  only when one article is clearly too narrow for what the user means.
- The output is a summary written for you to relay. Each edition gets a verdict (growing,
  declining, no clear change, or insufficient data), a confidence level with reasons, and
  caveats. It ends with `Saved:` (the run folder), `Re-run:` and `Next:`.

### 3. Report (when the user wants something shareable): `report`

1. Write `narrative.md` in the run folder from the `Saved:` line, in the user's language:

   ```
   # <the user's question>

   ## Bottom line
   <up to 3 sentences answering it>

   ## Next
   - <what to research next, and why: up to 4 bullets>
   ```

   Keep the three headings in English. Keep each bullet under 220 characters (about 30
   words) and the bottom line under 480. If the concept stands in for what the user asked
   about (the English language article for "learning English"), say so in the bottom line.
   Create the file with your file-writing tool, not with shell commands. The code adds the
   table, charts, and limitations.
2. Run `uv run SKILL_DIR/scripts/wiki.py report --run <run folder> --lang uk` (`--lang` is
   `en` or `uk` and sets the report's labels).
3. If it rejects the text, edit `narrative.md` as the error says and re-run; don't ask the
   user for permission to shorten it. A rejected number is one `analyze` didn't show.
   Numbers the user gave you, such as "we want 15% growth", go in `--user-numbers 15`.
4. Give the user the PDF path.

## Talking about the results

- Use only numbers the commands printed; rounding is fine. Don't compute new statistics:
  every figure in a report must trace back to the data.
- Give each edition's verdict with its confidence and the main reason. "No clear change" means
  the 90% range includes zero: say "no clear trend", not "declining".
- Mention the caveats that matter for the decision: proxies, renamed or new articles, spikes,
  tiny audiences.
- Don't guess why a spike happened (news, TV, school). Say that its cause is unknown, unless
  the user asks you to look it up.
- If the concept is a stand-in for what the user asked about, say so plainly, e.g. "views of
  the English language article, used as a proxy for interest in learning English".
- To answer "which audiences next", use the verdicts, sizes (views/month) and segments
  ("large & growing"), plus the user's own criteria, and explain why.

## Follow-up questions

Copy the `Re-run:` line and change one option: add an edition, change `--months`, add a
`--proxy`, or `--sort size`. Cached data makes this fast. For a new topic, start again at
`resolve`.

## Example

This topic is deliberately not one of the eval cases, so the example can't stand in for a
real run. Always start a new topic with `resolve`, even if you think you know its Wikidata ID:
IDs are easy to misremember.

User: "Is interest in chess growing in Spanish Wikipedia?"

1. `resolve "chess" --editions es` lists Q718 "chess: strategy board game" (es: Ajedrez), then
   the ABBA musical "Chess". The board game is clearly meant.
2. `analyze --concepts Q718 --editions es` prints: `DECLINING -20.9% [90% range -31.3% to
   -11.8%] · confidence HIGH · 20,664 views/month`, `consistent: 12 of 12 months below the
   same month last year`, and a caveat that all of Spanish Wikipedia changed by -20.9%.
3. Answer: "No. Chess's share of attention in Spanish Wikipedia fell 20.9% over the last 12
   months (90% range -31.3% to -11.8%), in all 12 months, so confidence is high. That already
   removes the drop in Spanish Wikipedia's total traffic. Pageviews show attention, not
   demand, so check other signals before building on this."

## More detail

- [references/methodology.md](references/methodology.md): how interest, growth, the 90% range
  and confidence are computed, and what each caveat means. Read it when the user asks how the
  numbers work or how far to trust them.
- [references/setup.md](references/setup.md): installing uv, running without uv, cache and
  environment variables.
