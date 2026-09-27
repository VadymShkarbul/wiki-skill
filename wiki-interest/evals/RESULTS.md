# Eval results

**Model:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), via Claude Code 2.1.267, headless and
isolated. Each run gets a fresh workspace with only this skill installed; the transcripts'
init events show `plugins: 0`, `mcp_servers: 0`.
**Date:** 2026-09-27. **Data:** Wikimedia pageviews through 2026-09-26.
**Run:** 10 cases × 3 runs, in [evidence/20260927-092602-haiku](evidence/20260927-092602-haiku)
(transcripts, grades, and artifacts including the PDFs; home and temp paths redacted).

## Summary

| | |
|---|---|
| Runs passed | **27/30** (90%) |
| Runs with ad-hoc code (own scripts, `curl`, `python`) | **0/30** |
| Cost | $1.52 total, $0.051 per run on average |
| Agent turns | 5.6 per run on average |
| Wall time | 31 s per run on average (the first run in a workspace includes dependency setup) |

Every run is graded deterministically ([run.py](run.py), [cases.json](cases.json)): skill used
or not, command order, required and forbidden flags, key facts in the answer, the answer's
language, PDF produced, no ad-hoc code, and every number in the answer printed by the tools.

## Per case

| Case | What it tests | Passed | Cost | Turns | Time |
|---|---|---|---|---|---|
| q1-fasting-pl-cs | Spec example 1: pl has no article, so give cs results and ask before any proxy | 3/3 | $0.047 | 5.0 | 35 s |
| q2-astronomy-uk-in-ukrainian | Spec example 2, asked in Ukrainian: verdict plus how far to trust it | 3/3 | $0.046 | 5.0 | 33 s |
| q3-english-report | Spec example 3: five editions plus a one-page PDF; "learning English" needs a stand-in | 3/3 | $0.068 | 7.7 | 44 s |
| followup-add-slovak-3y | Follow-up: add an edition and a longer window | 2/3 | $0.067 | 8.0 | 39 s |
| followup-proxy-yes | Follow-up: the user approves the proxy, so `--proxy` is used only now | 3/3 | $0.062 | 7.0 | 40 s |
| followup-report-in-ukrainian | Follow-up: PDF with Ukrainian labels | 2/3 | $0.071 | 8.7 | 43 s |
| ambiguous-mercury | Several meanings: ask, or state the assumption | 3/3 | $0.035 | 4.0 | 16 s |
| topic-in-ukrainian | Topic written in Ukrainian | 3/3 | $0.045 | 5.0 | 28 s |
| country-code-cz | `cz` instead of `cs` | 2/3 | $0.044 | 5.0 | 25 s |
| negative-grammar-fix | Mentions Wikipedia but needs no data: the skill must not trigger | 3/3 | $0.020 | 1.0 | 5 s |

## The 3 failures

| Run | What happened | Classification | Follow-up |
|---|---|---|---|
| country-code-cz #1 | Wrote "(90% range -3.8% to +33.8%)" for an edition comparison that the summary gave in points, without a unit | Minor model error, invited by an unlabeled range | The summary now prints "points". Confirmation run, separate: **3/3** ([evidence/20260927-093040-haiku](evidence/20260927-093040-haiku)) |
| followup-add-slovak-3y #2 | Found that pl and sk have no article and analyzed cs alone over 36 months | **Grader too strict:** valid behavior | Check loosened to "sk requested in any command". Re-graded: 3/3. Counted as a failure above, because the run was graded before the fix |
| followup-report-in-ukrainian #3 | Said the confidence range is "tight (18 percentage points)", a width Haiku computed itself | **Genuine violation** of "don't compute new statistics" | Known limitation (below) |

## After the final run

The pre-hand-off code review found 3 more issues, fixed with tests:
- an in-budget narrative with 8 editions overflowed the page (charts now shrink to fit);
- the AMBIGUOUS cue fired on minor homonyms (chess vs an ABBA musical);
- `resolve --editions pl,cs astronomy` lost its topic.

The two cases these touch were re-run as confirmation, recorded separately from the final
evidence:
- ambiguous-mercury: **3/3** ([evidence/20260927-093623-haiku](evidence/20260927-093623-haiku));
- q3-english-report: **3/3** ([evidence/20260927-093640-haiku](evidence/20260927-093640-haiku)).

## Changes made to reach this

From the first eval (6/10) through three rounds at N=3 (26/30, 26/30, 27/30). Each change is
recorded with its transcript evidence in [iteration-log.md](iteration-log.md):

- Decision-critical cues moved from SKILL.md into the command output: "run it now, without
  --proxy", "a request to compare is not agreement to a proxy", "AMBIGUOUS: ...".
- Guarantees moved from the model into code: the PDF prints what was measured (D5), and
  narrative numbers are checked before rendering.
- Checker gaps fixed (paths, K/M magnitudes, abbreviations), and the harness allowed `Edit`.
- The SKILL.md example was replaced after it turned out to be the same topic as eval q2: one
  run copied its Wikidata ID and skipped `resolve`. The final run uses an example (chess in
  Spanish Wikipedia) that appears in no eval case.
- One case was widened after a run showed a second correct path (q3: the precise ESL concept
  plus a proxy offer). This was done openly and is noted in the case and in the log.

## Known limitations (seen in transcripts, not caught by the checks)

- **Stand-in wording in chat:** Haiku rarely says in its chat answer that "English language" is
  a stand-in for "learning English" (0 of 5 when checked). The PDF states it, by code.
- **Attention called demand:** answers sometimes say "demand signal" and add speculative causes
  ("headwinds", "platform migration"). Regex checks can't judge this; an LLM judge is on the
  [roadmap](../docs/roadmap.md).
- **Derived statistics:** one run computed a range width itself (the failure above).
- **Period wording:** one run described the compared period as "December 2024 - August 2026".
  The numbers were right, but the period text wasn't.

## Not measured yet

- **Other models and runtimes:** the planned OpenCode + OpenRouter portability run (decision E1)
  needs OpenCode and an OpenRouter key on the test machine. The skill has no Claude-specific
  code paths: OpenCode reads `.claude/skills/`, and the commands are plain CLI.

## Reproduce

```
uv run evals/run.py --model haiku --runs 3
```

Results vary between runs, because the model is not deterministic and pageview data advances
daily. The checks compare the answer with what the tools printed in the same run, not with
fixed numbers.
