# Decisions

Each entry covers context, the options considered, the choice, and why. Evidence is in
`research-data-sources.md`.

## Topic → articles resolution

Principle: anchor on the concept (a Wikidata item), not on titles. Wikidata sitelinks
guarantee that the Polish and Czech articles describe the same concept, and that is what
makes a comparison across editions valid.

### D1. Who picks the concept: code proposes candidates, the model picks
- **Context:** users name topics in their own words and language. Search is ambiguous:
  "astronomy" also matches a journal and a song.
- **Options:** the model guesses titles; the code auto-picks the top hit; **code returns
  candidates and the model picks**; the user supplies IDs.
- **Choice:** the code searches Wikidata in the user's language and returns 3–5 candidates.
  Each has a label, a description, its total wiki count, and the title in each requested
  edition (or "missing"). The model picks one, or asks the user when it's unclear. Direct
  input (a QID, a Wikipedia URL, or `lang:Title`) skips the search.
- **Why:** a cheap model is reliable at choosing from a short labeled list and unreliable at
  producing exact titles in foreign languages. Auto-picking fails silently.

### D2. Topic scope: 1..N concepts, the same set in every edition
- **Options:** always a single concept; **1..N concepts proposed by the model**; automatic
  expansion via categories or the Wikidata graph.
- **Choice:** one concept by default. For broad topics (e.g. astronomy) the model proposes a
  small set of concepts, used identically in every edition. Automatic expansion goes on the roadmap.
- **Why:** one article is a fragile proxy for a topic, since a single news spike or rename
  distorts it. Categories differ between editions, which breaks like-for-like comparison.
  How concepts are combined into one number is decided under metrics.

### D3. An edition with no article: mark "not covered", offer an opt-in proxy
- **Context:** plwiki has no article for intermittent fasting (Q1666254), and this is the spec's
  first example.
- **Options:** fail; count as zero; **mark not covered**; auto-substitute the nearest article.
- **Choice:** mark the edition "not covered", leave it out of the numeric comparison, and
  report it as a finding. The code lists the nearest local articles as possible proxies. A
  proxy is used only when the user approves it, and it is labeled "proxy" in charts and the report.
- **Why:** a missing article does not mean zero interest, so counting it as zero is false.
  Silent substitution changes the question ("therapeutic fasting" is not intermittent fasting).

### D1a. Revision: candidates sorted by Wikipedia coverage *(2026-09-27, from live runs)*
- **Context:** Wikidata search ranks by text relevance. For "Mercury" it put the Ford car brand
  first; the planet came 3rd and the chemical element wasn't in the top 4.
- **Choice:** from the search hits (up to 4× the limit), keep topic items. Rank exact label or alias
  matches first, then by the number of Wikipedias that cover them, a notability prior.
  Result for "Mercury": planet (250), element (176), Roman god (84).
- **Review fix:** sorting by coverage alone buried exact matches under popular prefix matches.
  Wikidata search is by label prefix, so "Go" showed Google and Gothenburg and dropped the Go
  programming language. Exact matches now come first.
- **Why:** the most widely known meanings come first, and the model still sees each of them and asks
  the user when more than one fits (D1).

### D3a. Revision: proxies only from broader concepts; text search dropped *(2026-09-27, from live runs)*
- **Context:** the first implementation fell back to full-text search inside the edition. Searching
  trwiki for "Learning English" returned unrelated articles, including an assassination article and
  a sexual-content article. Broader concepts gave sensible proxies (plwiki "Post" and "Dieta" for
  intermittent fasting).
- **Choice:** proxies are the edition's articles on the concept's broader concepts (Wikidata P279
  "subclass of", then P31 "instance of"), each labeled with its source concept. When there are none,
  the output says "no proxy found in this edition".
- **Why:** it's a principled, explainable relation, not a word match. An irrelevant or offensive
  proxy suggestion would undermine trust in the whole report.
- **Also added:** when no candidate fits, the `Next:` line tells the model to re-run with the
  concept's encyclopedic name (e.g. "English language" for "learning English"; see D5).

### D4. Title housekeeping: resolve and flag
- **Choice (v1):**
  - Always resolve input titles through normalization and redirects (batched).
  - Detect the article's creation date. If it falls inside the window, trim the window and flag it.
  - Detect renames inside the window and flag them.
  - Don't add redirect views.
- **Roadmap:** stitching the history of renamed titles; adding up redirect views.
- **Why:**
  - Creation dates cause fake growth: the cswiki article on intermittent fasting was created 2020-10-28.
  - Redirect views are small: "UK" gets 0.7% of the views of "United Kingdom". Adding them
    would cost about one request per redirect (enwiki "Intermittent fasting" has about 25).
- **To verify during implementation:** the API call for the rename (move) log.

### D5. Precise concept vs. one with full coverage: no extra machinery, plus a report rule
- **Context:** "English as a second or foreign language" (Q130192) exists in 14 wikis and
  has no pl/cs/uk article. "English" (Q1860) exists in 319 wikis but measures interest in the
  language generally.
- **Choice:** coverage of the requested editions is already part of each D1 candidate, so the
  model sees the trade-off. When a broader proxy concept is used, the report names it in plain words.

## Metrics

Evidence: 24 full months (2023-09 to 2026-08), `agent=user`:

| Article | Raw YoY | Share YoY | First vs last month (raw) | Theil–Sen, relative to median | Avg views/mo |
|---|---|---|---|---|---|
| cs Přerušovaný půst | −53.6% | −47.7% | −69.7% | −58%/yr | 183 |
| uk Інтервальне голодування | −76.1% | −66.4% | −85.5% | −108%/yr | 175 |
| uk Астрономія | −59.6% | −45.5% | −92.3% | −76%/yr | 559 |
| pl Astronomia | −16.1% | −9.6% | −58.8% | −36%/yr | 1,431 |

Takeaways: normalization shifts results by 6–14 points; comparing endpoints is distorted by
season (pl: September vs August); a linear slope relative to the median produces impossible
values below −100%. A 10-year daily series comes back in one request (3,653 rows).

### M1. Fetch daily data, analyze monthly *(default)*
- Daily data is kept for spike detection in the trust step. Trends use full calendar months only,
  which avoids the partial-month trap.

### M2. Interest = share of edition, with raw views shown alongside
- **Options:** raw views; **share of edition (views per million edition views)**; indexed
  (start = 100); per speaker or internet user.
- **Choice:** share of edition is the headline for momentum. Raw monthly views are shown
  for audience size. Numerator and denominator use the same agent and access type.
- **Why:** size ("how many readers") and momentum ("is attention growing") are different
  questions. Share removes edition size and platform-wide shifts: the ukwiki boom and bust,
  AI-driven declines, and bot reclassification.

### M3. Headline growth: trailing-12 YoY on share
- **Options:** first vs last month; **last 12 vs previous 12 months**; CAGR; seasonal decomposition.
- **Choice:** compare the last 12 full months with the previous 12, on share. For windows
  under 24 months, compare with the same calendar months one year earlier (fetching extra history).
  A Theil–Sen slope on log(share), reported as %/year, is a supporting number for the trust step.
- **Why:** it is neutral to seasonality, uses all the data, and fits in one sentence for a founder.
  The log scale keeps the slope's %/year above −100%.

### M4. Seasonality is handled by design *(default)*
- All comparisons are year over year. With at least 2 years of data, the report may name the
  seasonal peak month as an insight (launch timing).

### M5. Several concepts: sum over the concepts common to all compared editions
- **Options:** **sum of shares**; equal-weight average of per-concept indices.
- **Choice:** sum the share of the concepts present in every compared edition, and add a
  per-concept breakdown. A question about a single edition uses all its concepts.
- **Why:** like-for-like across editions, and the sum reads as "the topic's share of attention".
  Equal weights let a tiny article swing the result.

### M6. Ranking editions: transparent dimensions plus quadrant labels
- **Options:** a composite score; **dimensions plus a quadrant**; a user-weighted score.
- **Choice:** show size, share, growth, and confidence side by side. Label each edition
  "large & growing", "small & growing", "large & flat", or "declining". Sort by growth by default,
  and let the user change it. A user-weighted score goes on the roadmap.
- **Why:** the spec says users bring their own criteria for what is promising. A transparent table
  is easy to defend; an opaque score isn't.

### M7. Traffic scope *(default)*
- `agent=user` and `access=all-access`. The default window is the last 24 full months.
  A mobile/desktop split goes on the roadmap.

## Trust and confidence

"Can we trust it?" means three questions: is it real (not noise), is it steady (not one spike),
and is the data sound?

Evidence: prototype on 24 full months (2023-09 to 2026-08), share of edition, trailing-12 YoY:

| Article | Views/mo | YoY | 90% CI | Months up | Despiked YoY | Spike share |
|---|---|---|---|---|---|---|
| cs Přerušovaný půst | 146 | −47.7% | [−62%, −28%] | 1/12 | −34.4% | 10.6% |
| uk Інтервальне голодування | 165 | −66.4% | [−72%, −58%] | 0/12 | −66.7% | 1.4% |
| uk Астрономія | 437 | −45.5% | [−52%, −33%] | 2/12 | −46.2% | 0.1% |
| pl Astronomia | 1,198 | −9.6% | [−24%, +8%] | 3/12 | −11.9% | 1.3% |
| pl Język angielski | 7,913 | −9.8% | [−15%, −5%] | 3/12 | −10.1% | 1.4% |
| en Intermittent fasting | 9,250 | −50.4% | [−57%, −42%] | 0/12 | −50.5% | 2.4% |

Takeaways:
- A point estimate misleads: pl Astronomia's CI crosses 0.
- Spikes matter at low volume: cs is −48% with spikes and −34% without.
- Low volume is not automatically untrustworthy: uk intermittent fasting is consistent at 165/mo.
- Daily sums equal monthly totals exactly.

### T1. Hybrid approach
- **Options:** rule checklist only; statistics only; **a few statistics feeding a rule-based grade**.
- **Choice:** the code computes a CI, a consistency count, and spike sensitivity. Rules turn these
  into a direction plus a High/Medium/Low grade, with reasons written by the code.
- **Why:** the verdict can be explained in one line, and the model relays reasons instead of
  interpreting p-values.

### T2. Uncertainty: month-pair bootstrap
- **Options:** **resample the 12 YoY month pairs**; daily block bootstrap; Poisson CI.
- **Choice:** 2,000 resamples of the 12 (this year, last year) month pairs give a 90% CI for YoY growth.
  Two editions are compared by bootstrapping the growth difference on shared month indices.
- **Why:** it is cheap, reflects real (overdispersed) noise, and is seasonality-safe by construction.
  A Poisson CI assumes pure counting noise and comes out far too narrow.
- **Limitation (to state in reports):** 12 autocorrelated pairs can make the CI slightly narrow.
  A daily block bootstrap goes on the roadmap.

### T3. Verdict rules
- **Direction:** CI above 0 → growing; below 0 → declining; crossing 0 → no clear change.
  Two editions: if the CI of the difference crosses 0 → no clear difference.
- **Confidence:** start at High and drop one level for each issue, down to Low:
  - spike-driven: despiked YoY differs by more than 10 pp, or the direction flips;
  - inconsistent: fewer than 9 of 12 months agree with the direction (one-sided sign test p ≈ 0.07);
  - tiny volume: median below 100 views/mo, where one classroom or one undetected bot can
    create the pattern.
- **Insufficient data:** less than 12 months of comparison history, or a median below 30 views/mo.
- **Why these numbers:** the CI already measures noise, so volume only acts as a floor against
  single-actor effects. The bars are defaults; they can be tuned after evals.

### T4. Quadrant size axis: relative median split
- **Options:** **above or below the median of the compared editions**; a fixed threshold.
- **Choice:** relative split, with raw monthly views always shown next to it.
- **Why:** no arbitrary number, and it is always defined. Showing raw numbers prevents
  "large" from misleading when every compared edition is small.

### T5a. Revision: totals check with a 1% tolerance *(2026-09-27, found by the check itself)*
- **Context:** the exact daily-vs-monthly check (T5) failed on the first live run. Every edition
  checked differs in 2025-03 (about -0.12%) and 2026-04 (up to +0.29%).
- **Choice:** accept gaps up to 1% and show them as a caveat. Larger gaps stop the run. Analyses
  always use the daily sums, so numerator and denominator stay consistent.
- **Why:** an exact rule would block every analysis. The gaps are far smaller than any effect we
  report, and hiding them would be dishonest.

### T5. Defaults
- **Spike detection:** a day counts as a spike when it exceeds the rolling ±14-day median by more
  than 5·MAD and is more than 2× that median. The report lists the top 3 spike dates. The model
  must not guess causes; if asked, it marks them as unconfirmed.
- **Data events are caveats, not downgrades:** the 2025 bot reclassification, the `automated`
  class since 2020-04, article creation or rename (D4), and proxy concepts (D3/D5).
  The 2025 event falls inside almost every current window, and normalization partly absorbs it.
- **Built-in checks:** daily sum must equal the monthly total, months must be complete, and share
  must stay within bounds. The run fails loudly if any check breaks.

## Command interface

Design target: a cheap model (Haiku 4.5 class) loses track of long chains, misreads large JSON,
and invents numbers it has to compute. So: few calls, relay-ready output, an explicit next step,
and cheap follow-ups.

### I1. Three commands: `resolve` → `analyze` → `report`
- **Options:** many small commands; **three commands**; two commands with automatic resolution.
- **Choice:** `resolve` returns concept candidates (the D1 checkpoint). `analyze` fetches data and
  computes metrics, trust, and charts. `report` renders the shareable output. `analyze` also
  accepts QIDs or `lang:Title` directly, so follow-ups skip `resolve`.
- **Why:** each command is one clear step. Automatic resolution would bring back the silent
  auto-pick that D1 rejected.

### I2. Parameters as CLI flags
- **Options:** **flags**; a JSON spec file.
- **Choice:** `--concepts` and `--editions` are required. `--months`, `--proxy lang:Title`, and
  `--sort` are optional.
- **Why:** one call, and small models handle flags reliably. A spec file costs an extra call and
  invites quoting errors.

### I3. Output: a text summary plus `analysis.json`
- **Options:** **a compact text summary with the JSON saved to disk**; full JSON on stdout.
- **Choice:** about 30 lines of verdict lines ready to relay: direction, growth, CI, confidence
  with reasons, size, not-covered editions with proxies, caveats, saved paths, a `Re-run:` line
  with the exact command, and a `Next:` line. The full `analysis.json` is saved for `report` and tests.
- **Why:** the model relays sentences instead of computing numbers. The `Re-run:` line turns a
  follow-up into a one-flag edit.

### I4. Stateless commands, cache in the user cache dir, outputs in the working dir
- **Options:** **stateless plus a cache**; a stateful session file; a cache inside the skill dir.
- **Choice:**
  - No state between runs except cached data.
  - Each article's full daily history (since 2015-07-01) is fetched in one request and cached
    for 24 h. Wikidata and MediaWiki lookups are cached for 7 days.
  - The cache lives in the user cache dir (`~/.cache/...`, overridable with an env var).
  - Outputs go to `./wiki-signal/<run>/`.
- **Why:** window, sort, or re-analysis changes cost no requests. The spec's "everything in the
  skill dir" covers code and materials, not runtime data. A skill dir may be read-only.
  Hidden session state is easy for a small model to lose track of.
- **To verify during implementation:** that the full daily history since 2015 comes back in
  one request. 10 years returned 3,653 rows.

### I4a. Revision: outputs go to `./wiki-signal-runs/<run>/` *(2026-09-27)*
- **Context:** I4 said `./wiki-signal/<run>/`. In this repo `./wiki-signal/` is the skill dir
  itself, so dev runs from the repo root would have written outputs into the deliverable.
- **Choice:** the default is `./wiki-signal-runs/<run>/` (gitignored), overridable with `--out`.
  The run id is a UTC timestamp plus a short hash of the parameters.

### I3a. Revision: decision-critical cues live in the tool output too *(2026-09-27, evals)*
- **Context:** in evals, Haiku followed SKILL.md's "analyze covered editions first, then ask about
  the proxy" in only 1 of 4 runs, and once treated a comparison request as consent to a proxy.
- **Choice:** `resolve` and `analyze` print the rule at the point where it applies: run analyze
  now without `--proxy`, and don't treat a comparison request as agreement to a proxy.
  SKILL.md keeps the same rule with its reason.
- **Why:** a small model reads the latest tool output right before it acts. Re-run: 3/3.
  Evidence in `evals/iteration-log.md`.

### I5. Defaults
- Every error ends with an actionable `Next:` line, e.g. an unknown edition code suggests the
  closest valid codes.
- A missing article is a result, not an error (D3).
- One entry script with subcommands, runnable from any working dir.
- Summaries are in English; the model answers in the user's language. Report language is
  decided in the report step.

## Report and charts

Evidence (2026-09-26): fpdf2 2.8.8 requires Pillow, fonttools, and defusedxml. The first two already
come with matplotlib, so it adds about 1.6 MB. reportlab 5.0.1 adds about 4.7 MB plus
charset-normalizer. DejaVu Sans (bundled with matplotlib) covers Polish, Czech, and Ukrainian
glyphs, but not Hindi or Japanese.

Layout (A4 portrait, one page):
- title (the user's question) with editions, window, and date;
- bottom line (model);
- verdict table (code);
- chart A and chart B side by side (code);
- "What to research next" (model);
- assumptions & limitations (code);
- footer: data source (CC0), fetch date, re-run command, "attention ≠ demand".

### R1. PDF engine: matplotlib for charts, fpdf2 for the page
- **Options:** matplotlib only; **matplotlib + fpdf2**; reportlab; HTML→PDF (weasyprint, headless Chrome).
- **Choice:** matplotlib renders the charts; fpdf2 lays out the page: text wrapping, tables, a Unicode
  TTF font, and overflow detection so the report stays on one page.
- **Why:** about 1.6 MB of pure Python for proper layout. matplotlib-only text layout is fragile.
  HTML→PDF needs system libraries, which breaks reproducibility.

### R2. Charts: trend and a CI forest
- **A:** rolling 12-month share, indexed to 100 at the window start, one line per edition, spike days
  marked. The last point against the point 12 months earlier is exactly the headline YoY, so the chart
  and the text can't disagree.
- **B:** YoY growth with its 90% CI per edition and a zero line. This is the trust verdict made visual.
- Charts are produced by `analyze`, so they can be shown in chat; `report` reuses them.
- **Rejected:** raw monthly lines (they mix seasonality and edition size); a log scale (misread by
  founders); a single chart (it loses the trust picture).

### R2a. Chart details settled while building *(2026-09-27, dataviz skill checks)*
- Colors follow the edition's position in `--editions`, never its rank. Coloring in result
  order would repaint lines under `--sort` (the skill's "recolor-on-rank" anti-pattern).
- Chart A marks spike months only for editions whose verdict is spike-driven. On a 12-month
  rolling line, markers for every spike read as dashes and match no visible bump.
- Chart B keeps the axis symmetric around 0 and puts verdict labels in the margin with fixed
  margins. Stretching the axis to make room for labels implied values that don't exist.
- Proxy editions are labeled "pl (proxy)" on both charts, where the reader sees the number.
- Palette validated with the skill's checker: 8 categorical slots pass. The verdict colors are a
  polarity encoding (blue/orange with a neutral gray), so gray failing the categorical chroma floor
  is expected. Every row also states its verdict in words.

### R3. Code writes the numbers; the model writes the narrative, which gets checked
- **Code:** numbers, the table, charts, caveats, method notes, the footer.
- **Model:** the title, a bottom line of at most 3 sentences, and at most 4 "what to research next"
  bullets, written to `narrative.md` in the run dir. A file avoids shell-quoting problems with long
  text passed as flags.
- **Checks in `report`:** reject any number that isn't in `analysis.json` (within rounding), and any
  text over the layout budget. Each rejection ends with a `Next:` fix.
- **Roadmap:** check that direction words ("growing"/"declining") match each edition's verdict. It is
  fuzzy across languages.
- **Why:** this answers the spec's "verify conclusions" requirement in a deterministic way. Invented
  numbers can't reach the PDF, and the one-page limit is guaranteed.

### R3a. Revision: numbers are checked against the summary the model saw *(2026-09-27)*
- **Context:** R3 said "numbers not in `analysis.json`". That file holds hundreds of monthly
  shares and view counts, so almost any invented percentage would match one of them by chance.
- **Choice:** `analyze` saves its summary as `summary.txt`. `report` accepts a narrative number
  only if it is one the summary showed, or a normal rounding of one:
  - half-up and half-even (62.5 -> 62 or 63);
  - to hundreds or thousands for values of 100 or more (23,694 -> 23,700 or 24,000).
  Small counts 0-12 are always accepted.
  The parser handles `,` and space thousands separators (uk/pl/cs write "23 700"), decimal
  commas, and the Unicode minus sign.
- **Why:** it matches the instruction the model gets ("use only numbers shown here"), and it
  catches invented statistics. In the live test, "35% more promising" was rejected.
- **Found by testing Ukrainian:** the first version split "23 700" into 23 and 700 and rejected
  an honest narrative.
- **Unit-aware (review fix):** a percentage in the narrative must match a percentage the summary
  showed. "10 of 12 months" does not license "10%". Plain numbers may match either kind. Small
  counts 0-12 are exempt only when they are not percentages.
- **Not checked:** the summary's Saved/Re-run/Next lines and the run id. Their digits (paths,
  timestamps) would otherwise whitelist arbitrary numbers.
- **User numbers:** `report --user-numbers 15,5000` declares numbers that came from the user, such
  as a growth bar or an audience goal, so the report can state the user's own criteria. The spec
  says users bring their own definition of "promising". Undeclared, they are rejected.

### R4. Report language: `--lang`, with en and uk built in
- **Options:** English only; **a string table**; the model translates labels on each run.
- **Choice:** about 25 fixed labels live in one JSON file per language. en and uk are included, and
  adding a language needs no code change. The narrative is written in the user's language.
- **Limitation:** the font covers Latin, Cyrillic, and Greek scripts. Other scripts (Noto fonts)
  go on the roadmap.
- **Implemented (2026-09-27):** 38 labels per file, including chart texts. `report` redraws both
  charts from `analysis.json` in the chosen language, so a report can be rebuilt from a saved run
  with no network.
- **Known limitation:** code-generated caveats and reasons, and edition names from Wikimedia's
  site matrix, stay in English in a non-English report. Translating these templates goes on the
  roadmap.

### R5a. Settled while checking the rendered PDF *(2026-09-27)*
- Left-aligned text: fpdf's default justification stretched word gaps, badly in the footer.
- White chart background: the off-white chart surface showed up as panels on the white page.
- Verdict words in the table are in ink, not the series color (dataviz rule: text wears text
  tokens). Chart B carries the color.
- Header labels that break mid-word were reworded or widened ("Views per month").

### R5. Design exclusions *(default)*
No cream or off-white background, no italic accent words in headings, no numbered "01 / 02" section
labels, no monospace labels, no pill badges, no gradients, shadows, or 3D, no pie charts, no dual
y-axes, no rainbow palettes, no red/green for direction (use blue = growing, orange = declining,
grey = no clear change; colorblind-safe), no heavy gridlines, and at most one accent color.
Chart titles state the finding, not the metric name.

## Stack and reproducibility

Evidence (2026-09-26, uv 0.8.18):
- `uv lock --script` produced `wiki.py.lock` with 15 pinned packages.
- `uv run <dir>/scripts/wiki.py` worked from another working directory with the skill dir read-only
  (`chmod -R a-w`). The environment lives in the uv cache, and imports of the local package work.
- A cold run (Python and packages downloaded) took 4.6 s; a warm run took 0.2 s.
- `uv export --script` produced a hashed `requirements.txt` (606 hashes).
- The system `python3` 3.7 on the dev Mac failed HTTPS with SSL certificate errors.

### S1. Python 3.11+, managed by uv
- **Why:** Python has the best chart and PDF ecosystem here. Go would need compiled binaries, which
  the spec forbids. We can't rely on the user's system Python.

### S2. PEP 723 inline dependencies plus a script lockfile
- **Options:** requirements.txt + pip; pyproject + uv.lock (project mode); **PEP 723 + `wiki.py.lock`**.
- **Choice:** `uv run <skill>/scripts/wiki.py <command>`. The lockfile pins every package.
  Fallback without uv: a hashed `requirements.txt` exported from the same lock, plus a venv recipe in
  `references/`. A test checks that the export matches the lock.
- **Why:** one short command, fully locked, and it works in a read-only skill dir. Project mode
  creates `.venv` inside the skill dir.

### S3. Runtime dependencies: matplotlib and fpdf2 only
- numpy (pulled in by matplotlib) covers bootstrap, medians, and Theil–Sen. No pandas (about 40 MB)
  and no requests: stdlib `urllib` with retry and backoff, honoring `Retry-After`.
- Requests go out one at a time, as Wikimedia advises. The cache makes repeat runs cheap.
- Dev tools `pytest` and `ruff` run pinned via `uv run --with ...` and are kept out of the runtime lock.
  Tests run offline against recorded API responses.

### S4. Everything inside the skill dir
- **Options:** **everything inside the skill dir**; code in the skill, docs at the repo root.
- **Choice:** the skill dir holds code, references, assets, tests, evals, and docs. The repo root
  keeps only dev-process files (`CLAUDE.md`, `TASKS.md`) and a pointer README. The empty
  PyCharm-generated root `pyproject.toml` was deleted.
- **Update (2026-09-27):** before publishing, the author removed `CLAUDE.md` and `TASKS.md`. The
  repo root now holds the README, the LICENSE, and the Claude Code marketplace file.
- **Why:** this is the strict reading of "all own materials and code must be in the skill
  directory". It costs nothing at runtime, because agents load only `SKILL.md` and read other files
  on demand.

### S5. Name: `wiki-signal`
- Lowercase with hyphens, and it matches the directory name. `wikipedia-interest` was avoided
  because a skill with that name is already installed in this environment.

### S6. Distribution: a plain skill folder, plus a Claude Code plugin *(2026-09-27)*
- **Choice:**
  - `wiki-signal/` works as-is as a skill folder: Claude Code (`~/.claude/skills/`,
    `.claude/skills/`), Codex (`~/.agents/skills/`, `.agents/skills/`), and OpenCode.
  - For one-command installs in Claude Code, `wiki-signal/.claude-plugin/plugin.json` (with
    `"skills": ["./"]`) makes the same folder a plugin. `.claude-plugin/marketplace.json` at the
    repo root lists it.
- **Why:** there is one source of truth, and the manifest sits inside the skill folder, so S4 holds.
- **Verified:**
  - `claude plugin validate` passes for both manifests;
  - a headless Haiku run loaded it with `--plugin-dir` as `wiki-signal:wiki-signal` and
    answered correctly;
  - a symlinked project skill worked too.
- **Codex:** not run here (not installed). Format and paths come from its docs. Its sandbox has no
  network by default, so setup.md explains the approval and `network_access` options. The pageview
  cache falls back to the temp dir when `~/.cache` isn't writable.
- **Licence:** MIT (the author's choice), in `LICENSE` at the repo root and in the skill folder.
- **Open:** a GitHub remote, which the marketplace command needs; the author pushes it.

## Testing on a cheap model

Evidence (2026-09-26, Claude Code 2.1.267):
- `claude plugin eval` exists but reports "currently in early access" and doesn't run for this account.
- `claude --bare -p` needs `ANTHROPIC_API_KEY` (it skips the claude.ai login), and it didn't load the project skill.
- `claude -p --model haiku --setting-sources project --strict-mcp-config`, run in a temp workspace
  that contains only `.claude/skills/<skill>/`, works:
  - the probe skill loaded;
  - the globally installed `wikipedia-interest` skill and all plugins were excluded;
  - the stream-json transcript was complete;
  - cost was $0.10 for 9 turns.
- Probe failure (Haiku 4.5, one tiny skill):
  - The script crashed with a raw traceback. The cause was HTTP 400: a monthly request whose end
    date falls inside the first month.
  - Haiku misdiagnosed it ("no hour 28"), then improvised: it read the source, tried curl, and wrote
    its own Python. That is exactly the ad-hoc-code behavior the spec forbids.
  - It also used `cd <skill> && uv run ...`, and that compound command doesn't match `Bash(uv run *)`
    permissions.

### E0. Lessons adopted into the design
- Every command catches errors and prints `Error: <real cause>` plus `Next: <action>`. No raw tracebacks.
- A hard rule in SKILL.md: if a command fails, report the error and its Next step; never write
  your own fetching or analysis code.
- SKILL.md gives exactly one invocation form: `uv run <skill-dir>/scripts/wiki.py ...`, runnable
  from any working dir, with no `cd`.

### E1. Harness: isolated Claude Code headless on Haiku, plus an OpenCode smoke test
- **Options:** **Claude Code headless with our own runner**; plus OpenCode with an OpenRouter model;
  `claude plugin eval` (unavailable).
- **Choice:** `evals/run.py` copies the skill into a temp workspace and runs the isolated
  `claude -p --model haiku ...` command. It saves transcripts and grades them.
  As a secondary check, the 3 spec queries run once each via OpenCode (which reads `.claude/skills/`)
  with an OpenRouter model. The user installs OpenCode and sets the key.
  Migrating to `claude plugin eval` once it's available goes on the roadmap.
- **Why:** it's the realistic runtime, isolated from the dev machine's own skills. OpenRouter shows
  the skill isn't Claude-specific, as the spec suggests.

### E2. Eval cases (about 10)
- The 3 spec queries (pl/cs intermittent fasting: missing article; uk astronomy: trust;
  English learning: report).
- Follow-ups via `--resume`: "add Slovak and 3 years", "use the proxy for Polish", "report in Ukrainian".
- Edge cases: an ambiguous topic ("Mercury"), a topic asked in Ukrainian, an invalid edition ("cz"),
  and a negative non-trigger case.
- **To verify during implementation:** `--resume` in isolated mode.

### E3. Grading: deterministic checks plus human review
- Transcript and artifact checks:
  - the skill fired;
  - commands ran in the order resolve → analyze → report;
  - **no ad-hoc code**: no written `.py`, and no `curl`, `python -c`, or `python3`;
  - numbers in the final answer are a subset of `analysis.json`;
  - direction words match the verdicts;
  - case-specific facts are present;
  - the PDF exists and has one page.
- Human review of the 3 spec transcripts goes in `evals/RESULTS.md`. An LLM judge goes on the roadmap.
- **Why:** free, repeatable, and defensible. A judge adds cost and needs verification itself.

### E4. Runs: N=3 for final evidence, N=1 while iterating
- The final evidence reports pass rate, cost, turns, and time per case on Haiku.
- Every SKILL.md change triggered by an eval failure is logged. That log is the
  "how AI output was verified" story.
