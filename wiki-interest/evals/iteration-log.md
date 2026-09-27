# SKILL.md iteration log

Every change to `SKILL.md` driven by a run on a cheap model, with the evidence. Runs use the
isolated harness from decision E1: `claude -p --model haiku --setting-sources project
--strict-mcp-config` in a temp workspace that holds only this skill.

## 2026-09-27: smoke runs while writing SKILL.md (Claude Haiku 4.5, N=1 unless noted)

| # | Prompt (spec query) | SKILL.md version | Behavior | Cost, turns |
|---|---|---|---|---|
| 1 | Q2: astronomy in uk, can we trust it? | first draft | `resolve` then `analyze` with the exact absolute-path command, no `cd`, no ad-hoc code. Numbers, verdict, confidence and reason relayed correctly, plus the "attention is not demand" caveat and a PDF offer. | $0.085, 5 |
| 2 | Q1: intermittent fasting pl vs cs | first draft | Reported pl as not covered, explained the proxy "Post" (fasting in general), asked before using it. But gave no Czech results, although they were available. | $0.091, 4 |
| 3 | Q1 | + "don't make the user wait: analyze covered editions now and offer the proxy in the same answer" | **Regression:** ran `--proxy pl:Post` without consent, and the bottom line blurred "fasting" into "intermittent fasting". "Offer the proxy" was read as "use the proxy". | $0.042, 5 |
| 4 | Q1, N=2 | numbered steps: analyze **without** `--proxy`, name the proxy and what it measures, add it only in a later run after a yes | No proxy used without consent in 2/2 runs. Results first, then the proxy offer, in 1/2; the other run asked before analyzing (safe, less useful). | $0.039 + $0.031, 5 + 4 |

**Lesson:** for a small model, "offer X" next to a flag it has just read is an instruction to
use X. Ordered steps with an explicit "without" and "only after" are followed; soft phrasing is
not. The results-first behavior is still 1/2 and is measured properly in step 6 (N=3).

## 2026-09-27: eval suite, `evals/run.py`, 10 cases from `evals/cases.json` (Haiku 4.5)

Before the first run, the grader was checked on transcripts with known outcomes. It failed the
proxy-without-consent regression (smoke run 3) and the early probe where Haiku wrote its own
Python and `curl`. It passed the good smoke runs.

### Iteration 1: 6/10 passed, $0.57 (`runs/20260927-085344-haiku`)

| Failure | Cause | Change |
|---|---|---|
| q3-english-report, followup-report-in-ukrainian: "answer numbers were printed" | **Grader false positive.** The answers quote the PDF path, and the run id in it (`20260927-085407`) was read as numbers. Behavior was right. In q3, `report` rejected an over-long narrative and Haiku shortened it and re-ran on its own, so the check loop works. | Grader ignores file paths. Re-graded offline: both pass. |
| q1-fasting-pl-cs, topic-in-ukrainian: no `analyze` in turn 1 | **Behavior.** With pl NOT COVERED, Haiku asked about the proxy before giving the covered edition's results, in 3 of 4 runs across smoke and eval. SKILL.md said to analyze first, but the tool output, the last thing the model reads, didn't. | `resolve` output now says it: "Run it now, without --proxy: the covered editions' results don't need the user's answer. Then ... offer the proxy." |

### Re-runs of the failing cases: q1 1/2, topic-in-ukrainian 2/2, followup-proxy-yes 1/1

- Analyzing first now works. But one q1 run then **re-ran with `--proxy pl:Post` on its own**,
  labeled as a proxy but without asking. It treated "compare Polish" as consent to a Polish proxy.
- Change: `analyze` output for a not-covered edition now says "ask ... stop there. A request to
  compare this edition is not agreement to a proxy: add --proxy only after the user says yes in a
  new message." SKILL.md got the same sentence.
- Re-run q1 x3: **3/3**. It analyzes first, gives the Czech results, asks about the proxy, and
  doesn't use it.

### Iteration 2: 9/10 passed, $0.55 (`runs/20260927-085926-haiku`)

| Failure | Cause | Change |
|---|---|---|
| ambiguous-mercury: "85" not printed | **Checker gap, shared with `report`.** "85K" is 85,080 views rounded to thousands, which is legitimate. `report` would also have rejected "about 85K readers". | The number check understands K/thousand/тис. and M/million/млн. Tests added: "24K" for 23,694 passes, "35K" is rejected. Re-graded offline: passes. |

With the checker fixed, iteration 2 is 10/10. No run in either iteration wrote ad-hoc code.

**Lessons:**
1. Put decisive instructions in the tool output next to the moment of decision. Haiku followed
   the `resolve` and `analyze` output more reliably than SKILL.md.
2. Name the exact reasoning error. "Only if the user agrees" wasn't enough; "a request to
   compare this edition is not agreement to a proxy" was.
3. Check the checker. 3 of the 5 red results were grader or checker bugs, not model failures.
   Each was confirmed by reading the transcript before anything was changed.

### Review of the harness (code review before hand-off)

- Grader fixes: skill commands with uv flags (`uv run --quiet ...`) were not recognized. Outputs
  of failed commands no longer count as "printed", because `report`'s rejection message quotes
  the very numbers it rejected. A crash in one case no longer loses the whole summary.
- Product fix: `resolve`'s "Run it now" cue is printed only when there is a single candidate.
  With several candidates it could have overridden "if more than one fits, ask the user" (D1).
- Iteration 2 transcripts re-graded with the corrected grader: still 10/10.
