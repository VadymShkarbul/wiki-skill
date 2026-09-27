# wiki-skill

This repository holds one Agent Skill: **[wiki-interest](wiki-interest/)**. It analyzes
Wikipedia pageviews to help B2C founders decide which topics to build next and which languages
to launch in, with trend verdicts, confidence, charts, and a one-page PDF report.

Everything the skill needs lives in `wiki-interest/`. Start with its
[README](wiki-interest/README.md).

Install in Claude Code as a plugin (use the local path until the repo is on GitHub):

```
claude plugin marketplace add VadymShkarbul/wiki-skill   # or: /path/to/wiki-skill
claude plugin install wiki-interest@wiki-skill
```

For Codex, or a plain skill folder, copy `wiki-interest/` to `~/.agents/skills/` (Codex) or
`~/.claude/skills/` (Claude Code). See [Install](wiki-interest/README.md#install).

The repo root only holds files for developing it with Claude Code: [CLAUDE.md](CLAUDE.md)
(working rules) and [TASKS.md](TASKS.md) (the plan).
