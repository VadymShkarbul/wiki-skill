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

Needs [uv](https://docs.astral.sh/uv/) and internet access. Dependencies are pinned in
`scripts/wiki.py.lock` and installed on first run. Without uv, see
[references/setup.md](references/setup.md).

### Claude Code

| Scope | How |
|---|---|
| Plugin (recommended) | `claude plugin marketplace add VadymShkarbul/wiki-skill` once the repo is on GitHub, or `claude plugin marketplace add /path/to/wiki-skill` from a local clone. Then `claude plugin install wiki-interest@wiki-skill`, or use `/plugin` inside Claude Code. The skill appears as `wiki-interest:wiki-interest`. |
| Personal | `cp -R wiki-interest ~/.claude/skills/` (or symlink it: `ln -s "$PWD/wiki-interest" ~/.claude/skills/wiki-interest`) |
| One project | Put it at `.claude/skills/wiki-interest/` in that repo |

Verified on 2026-09-27 with Claude Code 2.1.267:
- `claude plugin validate` passes for both `wiki-interest/` and the marketplace at the repo root;
- a headless Haiku run with `--plugin-dir wiki-interest` answered correctly;
- a symlinked project skill answered correctly.

### Codex

| Scope | How |
|---|---|
| Personal | `cp -R wiki-interest ~/.agents/skills/` |
| One repo | Put it at `.agents/skills/wiki-interest/` in that repo |

Codex reads the same `SKILL.md` format and picks the skill from its description, or you can
mention it as `$wiki-interest`. Codex's default sandbox has **no network**, and it writes only to
the workspace and `/tmp`, so approve the prompts for `uv run` or start Codex with
`-c 'sandbox_workspace_write.network_access=true'` (details in
[references/setup.md](references/setup.md)). The skill never writes into its own folder, so a
read-only `.agents/` is fine. Not yet run end to end in Codex here (roadmap, E1).

### Other agents

OpenCode reads `.claude/skills/` and `.agents/skills/`. Any agent that supports Agent Skills and
can run shell commands can use it.

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
