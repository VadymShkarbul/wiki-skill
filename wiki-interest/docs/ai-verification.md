# How AI output was verified

The skill was built with Claude Code (Claude Opus) as the main tool. It wrote research probes,
code, tests, documents and eval harnesses, and it ran a code review before every hand-off. The
rule throughout was that nothing it produced counted as done until something independent
confirmed it: a live API response, a second implementation, a test, a rendered file, a
cheap-model run, or the author's own decision. This page lists those checks and what they
caught.

## 1. Decisions stayed with the human

Every design choice was presented as options with trade-offs and a recommendation, and the
author chose. There were 7 areas and about 40 decisions, each logged with context, options,
choice and reason in [decisions.md](decisions.md). When a later step showed an earlier decision
was wrong, the AI proposed a revision instead of silently working around it. These revisions are
logged as D1a, D3a, T5a, I3a, I4a, R2a, R3a and R5a, each with its evidence.

## 2. Facts about the data were checked live, not recalled

- Every claim about Wikimedia APIs was probed with real requests and recorded in
  [research-data-sources.md](research-data-sources.md), with the source. Unconfirmed points were
  marked as such and resolved later. For example, "missing daily rows mean 0 views" was
  confirmed by summing daily rows against monthly totals.
- Probes found the traps the design is built around: Polish Wikipedia has no article for the
  spec's first topic, monthly queries silently include partial months, whole editions swing by
  ±50%, and Wikimedia reclassified bot traffic in 2025.
- A research subagent claimed `claude plugin eval` needs a newer Claude Code version. Running it
  locally showed the command exists but is in early access. The claim was corrected before
  anything relied on it.

## 3. Numbers were cross-checked by a second implementation

- A throwaway prototype, written separately during the trust design, computed growth, the 90%
  range and despiked growth. The production engine was then run on the same window and matched it
  exactly (e.g. cs intermittent fasting -47.7% and -34.4%). The 90% ranges were within 1 point,
  with the difference explained by random draws.
- A live test pins a value read by hand from the API (enwiki "Astronomy", January 2024: 43,527).
- A built-in check compares summed daily totals with Wikimedia's own monthly totals. On its first
  live run it found a real inconsistency (2025-03 and 2026-04 differ in every edition checked),
  which became decision T5a.

## 4. Code was tested, linted and reviewed

- 126 offline tests. API tests replay responses recorded from the live APIs, so they're
  deterministic. Statistics tests use known inputs and outputs.
- ruff with `select = ["ALL"]`. Every ignore has a written reason.
- A code review of every step's diff before hand-off: 21 findings over 6 reviews, all fixed,
  each with a regression test where it applied. Examples:
  - connection drops mid-response were not retried;
  - a sort that dropped exact matches ("Go" lost the Go language);
  - a crash for editions younger than the comparison;
  - a proxy for an edition outside `--editions` was silently ignored;
  - the number check could be passed by digits in file paths;
  - "10 of 12 months" licensed an invented "10%";
  - the grader accepted numbers that `report` had rejected.

## 5. Outputs were looked at, not assumed

- Charts were checked with the dataviz palette validator and then inspected as rendered images.
  That caught colors that followed rank instead of edition, a clipped title, a legend covering a
  line, and an axis stretched to fit labels.
- The PDF was rendered to images in English and Ukrainian and inspected. That caught justified
  text, off-white panels, colored verdict text, and headers breaking mid-word. Testing Ukrainian
  also caught that "23 700" (space as thousands separator) was split into two numbers.

## 6. The skill was tested on the model it is written for

- An isolated harness runs Claude Haiku 4.5 on 10 cases with only this skill installed
  ([run.py](../evals/run.py), [cases.json](../evals/cases.json)). The grader was validated on
  transcripts with known outcomes before being trusted. It failed the known-bad ones (ad-hoc
  `curl`/Python, a proxy used without consent) and passed the good ones.
- At one run per case, iterations went from 6/10 to 10/10. At three runs per case, the final
  rounds scored 26/30, 26/30, 29/30 (with a contaminated example) and 27/30. Every change is in
  [iteration-log.md](../evals/iteration-log.md). A transcript was read before each change.
  3 of 5 red results turned out to be grader bugs, not model failures, and one of my own
  SKILL.md edits caused a regression that the next run caught.
- Final evidence: 10 cases × 3 runs, **27/30**, with no ad-hoc code in any run. Each failure is
  classified in [evals/RESULTS.md](../evals/RESULTS.md), with the transcripts committed.

## 7. Mistakes the AI made, and what caught them

| Mistake | Caught by |
|---|---|
| Queried unrelated Wikidata IDs in a probe ("room", "siege") | Reading the output; redone with the real IDs |
| `ruff --fix --select RUF100` stripped every justified `# noqa` | Lint of the next run; restored from git and by hand, diff verified |
| A meaningless expression while computing spike share | Self-review before running; rewritten, then verified against the prototype |
| A test helper used a list as a dict key | The test run |
| A SKILL.md tweak ("offer the proxy") made Haiku use the proxy without consent | The next Haiku run |
| An `rm -rf` on a path built from a command substitution | Claude Code's safety check refused it; the command was rewritten |
| The SKILL.md worked example was the same topic as an eval case, so one run copied its ID and skipped a step | Reading the one failing transcript of an otherwise 29/30 run; the example was replaced and the suite re-run (27/30, the honest number) |

The pattern: the AI was fast and usually right, and every wrong case above was caught by an
independent check, not by trusting the author of the code.
