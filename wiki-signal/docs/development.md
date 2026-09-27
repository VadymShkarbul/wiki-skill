# Development

All commands run from the skill dir (`wiki-signal/`). Only `uv` is required.

| Task | Command |
|---|---|
| Run the CLI | `uv run scripts/wiki.py --help` |
| Offline tests | `uv run --no-project --python 3.11 --with-requirements requirements.txt --with pytest==9.1.1 pytest` |
| Live API checks | same, with `-m live` |
| Lint and format | `uvx ruff@0.16.9 check .` and `uvx ruff@0.16.9 format .` |
| Change dependencies | edit the `# /// script` block in `scripts/wiki.py`, then `uv lock --script scripts/wiki.py` and `uv export --script scripts/wiki.py --quiet > requirements.txt` |
| Check the lock is current | `uv run --locked scripts/wiki.py --version` |

`tests/test_lock.py` fails when `requirements.txt` drifts from `scripts/wiki.py.lock`.

## Environment variables

| Variable | Effect |
|---|---|
| `WIKI_SIGNAL_CACHE_DIR` | Cache location (default: `$XDG_CACHE_HOME/wiki-signal` or `~/.cache/wiki-signal`) |
| `WIKI_SIGNAL_CONTACT` | Contact in the User-Agent sent to Wikimedia (default: the author's GitHub URL) |

## Evals on a cheap model

Needs the `claude` CLI, logged in. Each run uses a fresh temp workspace that contains only
this skill, with user-level skills, plugins and MCP servers excluded.

| Task | Command |
|---|---|
| All cases, 3 runs each, on Haiku | `uv run evals/run.py --model haiku --runs 3` |
| One case while iterating | `uv run evals/run.py --case 'q1-*' --runs 1` |

Cases and checks: `evals/cases.json`. Results: `evals/runs/<stamp>-<model>/` (gitignored) with
`summary.md`, and per run the transcripts, the `result.json` grades, and artifacts. The final
evidence is kept in `evals/evidence/` and summarized in `evals/RESULTS.md`. Log every
SKILL.md change driven by a run in `evals/iteration-log.md`.
