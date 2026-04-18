# PROJECT_CONTEXT

**Project:** Brain-Wrought
**Owner:** Arron Street (independent; not affiliated with any commercial entity)
**Status:** Pre-build → Phase 0 (Apr 18-20, 2026)
**Target v1 public:** June 20, 2026
**Primary submission target:** Berkeley RDI AgentX-AgentBeats Phase 2

---

## 1. What is Brain-Wrought

Brain-Wrought is an independent open benchmark for personal AI knowledge systems — "personal brains" in the Garry Tan / Obsidian / second-brain-agent sense. It evaluates AI systems that read, maintain, and reason over a personal knowledge vault across three axes:

- **A. Retrieval** — does the brain find what's already filed?
- **B. Ingestion** — can the agent turn raw inbox content into a well-structured brain?
- **C. Assistant / personalization** — does the agent actually know the user?

Each axis yields a score with bootstrap confidence intervals. A weighted composite ranks submissions on a public leaderboard. Qrels, gold graphs, and actual judge rubrics live in a sealed private repo; fixtures are randomized per submission.

## 2. Why it exists

### 2.1 Benchmark gap

No current benchmark covers the full personal-knowledge-agent loop:
- RAGAS measures RAG quality generally, not personal knowledge
- MTEB is embeddings
- HELMET is long-context
- LongMemEval is conversational memory
- GAIA is general assistant (and Berkeley showed it's exploitable)
- PrivacyBench is privacy in personal AI
- PersonaBench / LaMP is persona/personalization
- gbrain eval is retrieval-only

Meanwhile, a dozen personal-brain-agent systems (Mem0, Cognee, COG, Smart2Brain, Obsidian-second-brain skill, gbrain forks) ship without a shared evaluation standard.

### 2.2 Exploitability crisis

Berkeley RDI published (April 11, 2026) that an automated scanning agent hit near-perfect scores on 7 of 8 major agent benchmarks without solving a single task. Brain-Wrought is designed from day one to resist these patterns via sealed qrels, fixture randomization, judge panel voting, rubric sealing, and held-out test sets.

## 3. Architecture

Four-layer decomposition: **Thin Harness / Fat Skills / Fat Code / Sealed Artifacts**

- `brain-wrought-harness` (this repo): pytest runner, CLI, submission intake
- `brain-wrought-skills`: markdown skills, public rubric scaffolds, submitter docs
- `brain-wrought-engine`: deterministic scoring
- `brain-wrought-sealed` (private): qrels, gold graphs, actual judge rubrics

See ADR-001 through ADR-004 in `brain-wrought-skills/adr/`.

## 4. Constraints

- **No monetization.** Federal ethics rules prohibit outside income for the owner. Prize money is permitted.
- **No commercial entity** attached to the benchmark.
- **Independent positioning.** Brain-Wrought presents as neutral, not under any commercial brand.

## 5. Success criteria

**Minimum** (v0.5, Week 2): Retrieval axis public, reference submission runs end-to-end, public leaderboard live.

**Target** (v1.0, Week 9): All three axes public, 3+ reference submissions, Docker container for full reproduction, AgentX Phase 2 submission complete, Arxiv preprint posted.
