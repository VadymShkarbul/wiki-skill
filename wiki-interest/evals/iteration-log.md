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
