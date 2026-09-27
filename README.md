# wiki-signal

This repository holds one Agent Skill: **[wiki-signal](wiki-signal/)**. It helps B2C
founders decide which topics to build next and which languages to launch in. Ask your agent a
plain question, and it answers from Wikipedia pageview data with a verdict per language, how far
to trust it, charts, and a one-page PDF report.

![How wiki-signal works: the model reads the question, picks the concept, relays verdicts and writes the narrative; three commands (resolve, analyze, report) compute every number](wiki-signal/docs/images/how-it-works.png)

The model decides and words things; the code computes every number. That is why it works well
even on small, cheap models: 27 of 30 eval runs passed on Claude Haiku 4.5.

## Install

In Claude Code, as a plugin (use the local path until the repo is on GitHub):

```
claude plugin marketplace add VadymShkarbul/wiki-signal   # or: /path/to/wiki-signal
claude plugin install wiki-signal@wiki-signal
```

For Codex, or a plain skill folder, copy `wiki-signal/` to `~/.agents/skills/` (Codex) or
`~/.claude/skills/` (Claude Code). Needs [uv](https://docs.astral.sh/uv/) and internet access.

## Learn more

The [skill's README](wiki-signal/README.md) covers:
- how it works, step by step, with real output;
- what you get;
- how to read the results;
- install details;
- quality, limits and privacy.

Everything the skill needs lives in `wiki-signal/`. The repo root holds this README, the MIT
[LICENSE](LICENSE), and the Claude Code marketplace file (`.claude-plugin/`).
