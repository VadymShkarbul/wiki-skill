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

## 2026-09-27: final evidence round (Haiku 4.5, N=3)

### First N=3 run: 26/30, $1.65 (`runs/20260927-090506-haiku`)

N=3 exposed what N=1 hid: q3 (the report case) passed once in iteration 2 but failed 3/3 here.

| Failure | Transcript showed | Change |
|---|---|---|
| q3 run 2: asked "could you approve the edit?" | `report` rejected an over-long narrative; the fix needed `Edit`, which the **harness** didn't allow | Harness allows `Edit` (a real user would approve it) |
| q3 run 1: "permissions issue", no PDF | Tried to write `narrative.md` with `cat >` in Bash (blocked), then gave up | SKILL.md: create the file with the file-writing tool; don't ask permission to shorten it |
| q3, all runs: first narrative always too long | Bullets over 170 characters; one bottom line counted as 4 sentences because of "e.g."/"vs." | Limits stated in SKILL.md and relaxed to what the page fits (bullet 220, bottom line 480); abbreviations are not sentence ends |
| q3 run 3: no stand-in mention | The report was fine, but the "English language" article was never named as a stand-in for "learning English" (D5) | See below |
| ambiguous-mercury run 3 | Chose the planet without asking or naming other meanings; also tried `--editions English German` | `resolve` prints an explicit AMBIGUOUS line when several concepts match exactly; `--editions` accepts spaces too |

### Targeted re-runs

- ambiguous-mercury x3: **3/3**.
- q3 x3: a PDF was produced in 3/3, but the stand-in was stated in only 1/3 narratives and 0/3
  chat answers, even with a SKILL.md rule and a "Measured:" line at the end of the summary.
- Changes:
  - The PDF now prints a code-generated "Measured: views of the Wikipedia article on 'English'
    (Q1860) ..." line under the bottom line, so D5 holds in every report whatever the model writes.
  - The "Measured:" line moved to the top of the analyze summary, where it is relayed more often.
- The transcripts also showed qualitative issues no regex catches: "a strong signal of ...
  demand" (attention presented as demand), reading the ukwiki traffic decline as a cause
  although share already removes it, and speculative causes. These go to the roadmap (LLM judge).

### Second N=3 run: 26/30, $1.50 (`runs/20260927-091553-haiku`)

| Failure | Transcript showed | Verdict and change |
|---|---|---|
| q3 run 1: no Q1860, no PDF | Picked the more precise concept (ESL, Q130192), analyzed de and tr (the only editions with it), and asked whether to use "English language" as a proxy for pl, cs, uk | **Correct under D3/D5**; the case was too narrow. q3 now accepts two paths (`any_of`): English language + PDF, or ESL + results + proxy offer without `--proxy` |
| q3 runs 2-3: no stand-in in the chat answer | PDF produced; neither answer nor narrative says "stand-in" | **Model limitation, kept visible:** 0/5 chat answers stated it, even with the cue at the top of the summary. D5 is enforced where it is required, in the PDF, by the code-printed "Measured:" line. In the report path the eval now checks that a PDF exists |
| followup-proxy-yes run 2: "24" not shown | "Last 24 Months": the window length appeared only in the Re-run line, which the grader rightly ignores | **Product gap:** the summary now states the window length ("(24 months)") |

Re-grading the three q3 transcripts under the new case definition: 3/3 (1 ESL path, 2 PDF path).
The final evidence below comes from a fresh run on this code and these cases.

### Third N=3 run: 29/30, $1.54 (`runs/20260927-092104-haiku`)

- q2 run 1 skipped `resolve` and used Q333 directly. The **SKILL.md example was the same topic
  as eval q2** (astronomy, uk, Q333), so the model copied the ID. That is eval contamination,
  my mistake. It may also have helped earlier q2 passes.
- Change: the example is now chess in Spanish Wikipedia, which appears in no eval case, using
  real output from a live run. SKILL.md says to always start a new topic with `resolve`.

### Final run on the final example: 27/30, $1.52 (`evidence/20260927-092602-haiku`)

- q2 is now 3/3 *with* `resolve`, which is the honest number.
- The three failures (country-code-cz: an unlabeled points range written as %;
  followup-add-slovak: a grader that was too strict; followup-report-in-ukrainian: a
  self-computed range width) are analyzed in [RESULTS.md](RESULTS.md).
- Follow-ups:
  - the comparison range now prints "points"; confirmation run 3/3
    (`evidence/20260927-093040-haiku`);
  - the slovak check was loosened; re-graded 3/3.
- This run is the final evidence. It was not re-run to reach a perfect score.

### Review fixes after the final run, and their confirmation

The code review before hand-off found 3 issues: page overflow with 8 editions and an in-budget
narrative; AMBIGUOUS firing on minor homonyms ("chess" vs an ABBA musical); and `--editions`
swallowing the resolve topic. Fixes:
- charts shrink to the remaining space;
- a meaning counts as ambiguous only with at least 25% of the top meaning's coverage;
- the topic is recovered from trailing non-edition words.

Confirmation re-runs: ambiguous-mercury 3/3, q3-english-report 3/3 (in `evidence/`).
