# Tasks

- [x] Analyze the task spec and extract key points
- [x] Write CLAUDE.md
- [x] Research data sources, see `wiki-interest/docs/research-data-sources.md`
- [x] Brainstorm architecture options and record decisions in `wiki-interest/docs/decisions.md`
  - [x] Topic → articles resolution (D1–D5)
  - [x] Metrics (M1–M7)
  - [x] Trust and confidence (T1–T5)
  - [x] Command interface (I1–I5)
  - [x] Report and charts (R1–R5)
  - [x] Stack and reproducibility (S1–S5)
  - [x] Testing on a cheap model (E0–E4)
- [ ] Implement the skill
  - [x] 1. Foundation: entry script + lock, HTTP client (UA, spacing, retries), cache, CLI skeleton
  - [x] 2. `resolve`: Wikidata candidates, coverage, proxies (creation date/rename checks move to step 3: they need the window)
  - [x] 3. `analyze`: fetch, share, YoY, trust verdict, creation/rename checks, charts, summary + analysis.json
  - [x] 4. `report`: one-page PDF, narrative checks, en/uk labels
  - [x] 5. SKILL.md + references (methodology, setup); smoke-tested on Haiku, see `wiki-interest/evals/iteration-log.md`
  - [ ] 6. Eval runner + cases; iterate on Haiku (N=1)
  - [ ] 7. Final evidence (N=3 + OpenCode smoke); roadmap; AI-verification notes
- [ ] Test on a cheap model (Haiku 4.5 / OpenRouter) with the three spec queries
- [ ] Write the roadmap and the AI-verification notes

## Notes for later steps
