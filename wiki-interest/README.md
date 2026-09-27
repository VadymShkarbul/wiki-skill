# wiki-interest

An Agent Skill that helps B2C founders decide which topics to build next and which languages to
launch in. It measures how interest in a topic changes across Wikipedia language editions, says
how far each trend can be trusted, and produces a one-page PDF report.

Pageviews measure attention on Wikipedia, not demand. Results are signals of what to validate
next.

## What it answers

- "Compare the growth of interest in intermittent fasting in Polish and Czech Wikipedia over
  the last two years."
- "Is interest in astronomy growing in Ukrainian Wikipedia, and how much can we trust it?"
- "Compare interest in learning English across our chosen editions and prepare a short report:
  which audiences should we research next, and why?"

## Install

Copy this folder to where your agent loads skills, e.g. `~/.claude/skills/wiki-interest/` or
`.claude/skills/wiki-interest/` in a project (OpenCode reads the same paths). It needs
[uv](https://docs.astral.sh/uv/) and internet access. Dependencies are pinned in
`scripts/wiki.py.lock` and installed on first run. Without uv, see
[references/setup.md](references/setup.md).

## How it works

The agent reads [SKILL.md](SKILL.md) and runs three commands:

| Command | Does |
|---|---|
| `resolve "<topic>" --editions pl,cs` | Finds the Wikidata concept and its article in each edition. Flags editions without one and suggests proxies the user may approve. |
| `analyze --concepts Q… --editions pl,cs` | Computes interest as share of each edition's human pageviews, year-over-year growth with a 90% range, a verdict and confidence per edition, caveats, and two charts. |
| `report --run <folder> --lang en\|uk` | Renders a one-page PDF. It first checks that every number in the model's narrative was produced by the analysis. |

Run any of them as `uv run scripts/wiki.py <command> --help`.

## Evidence

- Evals on Claude Haiku 4.5: [evals/RESULTS.md](evals/RESULTS.md), with the iteration history
  in [evals/iteration-log.md](evals/iteration-log.md).
- Design decisions and their evidence: [docs/decisions.md](docs/decisions.md).
- API behavior as probed: [docs/research-data-sources.md](docs/research-data-sources.md).
- How AI-written output was verified: [docs/ai-verification.md](docs/ai-verification.md).
- What comes next: [docs/roadmap.md](docs/roadmap.md).

## Layout

```
SKILL.md            agent instructions
scripts/            wiki.py (entry, inline deps) + wiki.py.lock + wiki_interest/ package
references/         loaded on demand: methodology.md, setup.md
assets/i18n/        report labels (en, uk)
requirements.txt    hashed fallback for installs without uv
tests/              offline tests on recorded API responses
evals/              cheap-model eval harness, cases, results
docs/               decisions, research, roadmap, verification, development
```

Development commands: [docs/development.md](docs/development.md).
