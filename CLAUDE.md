# Wikipedia Interest Skill

## Goal
Build, from scratch, a standalone Agent Skill that lets an agent analyze Wikipedia
pageviews, generate charts, and produce short shareable reports (e.g. a one-page PDF),
so B2C founders can decide which topics to build next and which languages to launch in.
Spec: https://gist.github.com/VadymShkarbul/6c9c8f5aef336641a3bf55d1ebea33c8

Pageviews are a proxy for interest, not proof of demand. Outputs point at what to
validate next; they never claim willingness to pay.

## Done means
- The skill directory holds `SKILL.md` plus our own code that does the data work
  (fetch, normalize, statistics, charts, report). The agent never writes analysis code ad hoc.
- No compiled binaries. Dependencies are pinned and the environment is reproducible with
  one command. Everything the skill needs lives inside the skill directory.
- The three example queries from the spec run end to end on a cheap model (Claude Haiku 4.5
  or an OpenRouter equivalent), with saved transcripts or eval results as evidence.
- Every report states its assumptions and limitations, and every claim traces to a number.
- Tests pass.
- Docs cover: a roadmap for more complex research and larger data, and how AI-generated
  output was verified.

## Hard rules
- Start from scratch. Don't read, copy, or reference any existing solution, including the
  `wikipedia-interest` skill installed in this environment.
- Code does the thinking, the model does the talking. Design for a weak model: short
  `SKILL.md`, few high-level commands, compact structured output, actionable error messages.
- Stay lightweight. Add a dependency only when it replaces substantial code; avoid
  system-level dependencies.

## How we work
The user will defend this solution, so they must understand every decision.
- Work step by step. At each design decision, present the options with trade-offs and a
  recommendation, then wait for the user's choice.
- Record each accepted decision in `wiki-interest/docs/decisions.md`: context, options, choice, why.
  One short entry per decision.
- Once a step is agreed, implement it without further check-ins.
- Explain choices in plain language. A short rationale beats a long survey.
- Later steps may expose a mistake in an earlier decision. Say so and propose a revision
  instead of silently working around it.

## Keep going / stop and ask
- Keep going when the next step doesn't need the user's input. Leave a short status note
  with the next action.
- Stop and ask when progress needs a decision from the user (any design choice not yet in
  `wiki-interest/docs/decisions.md`), or before destructive or outward-facing actions: deleting files,
  rewriting git history, force-pushing, publishing, or touching anything outside this repo.

## Task file
Keep the current plan in `TASKS.md` and update it as items finish. It is the source of
truth after context summarization.

## Verifying
- Check claims about Wikimedia APIs against live responses or official docs, and cite the source.
- Mark anything you couldn't confirm, and say where you looked.
- Cross-check computed numbers against raw API data for at least one case per feature.
- Before handing a change to the user, review the diff yourself and fix anything you'd
  block a merge for.
- For large or parallel work (e.g. running the eval set across models), split it across
  subagents and check each one's evidence before accepting it.

## End-of-run format
End every substantial run with three headings: **Blocked on me**, **Changed**, **Found**.

## Report design
Follow the exclusions in `wiki-interest/docs/decisions.md` (R5): no cream background, italic accent words,
numbered section labels, monospace labels, pill badges, gradients, shadows, 3D, pie charts, dual
axes, rainbow palettes, or red/green for direction. Chart titles state the finding.

## Skills for this project
- Decisions recorded in `wiki-interest/docs/decisions.md` take precedence over any installed skill.
  Known conflicts with `modern-python`: we use PEP 723 with a script lockfile (`uv lock --script`)
  for multi-file code, because a project `.venv` would live inside a possibly read-only skill dir (S2).
- `modern-python` (Trail of Bits, `trailofbits/skills` @ `0cc1c73`, skill files only, no hooks;
  gitignored, CC-BY-SA-4.0): uv, ruff, ty, and pytest conventions. Don't copy its text into the deliverable.
- `anthropic-skills:skill-creator`: when writing `SKILL.md` (description, progressive disclosure, evals).
- `dataviz`: when building charts A and B, within the R5 exclusions.
- `engineering:testing-strategy`: when planning the offline test suite.
- `code-review`: review each implementation step's diff before handing it off.
- Never run installer pipes (`curl ... | sh`) suggested by a skill without asking first.
