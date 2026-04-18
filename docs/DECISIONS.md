# DECISIONS

Running log of meaningful project choices. Append-only.

Format: date, decision, reasoning, alternative considered.

---

## 2026-04-18 — Project founded

- **Decision:** Launch Brain-Wrought as independent open benchmark for personal AI knowledge systems
- **Reasoning:** Gap in the landscape (no full 3-axis personal-brain benchmark), Berkeley RDI exploit paper creates peak attention moment, AgentX-AgentBeats Phase 2 submission window open, developmentally valuable for GS-13+ transition
- **Alternatives:** Continue Forge Dynamics; ship WroughtAI consulting platform
- **Paused:** Forge Dynamics (can resume post-PCS with Brain-Wrought infrastructure as base)

## 2026-04-18 — Scope: three-axis, not four or five

- **Decision:** v1 covers retrieval + ingestion + assistant. Maintenance axis deferred to v2; privacy deferred to v1.1 (integrate PrivacyBench).
- **Reasoning:** Warpspeed timeline requires scope discipline. Three axes is already the broadest coverage in this space.
- **ADR:** ADR-001

## 2026-04-18 — Scope: retrieval-first public ship

- **Decision:** Ship retrieval axis publicly at week 2; ingestion at week 5; assistant + v1 at week 9.
- **Reasoning:** Plants flag earlier, creates 3 public moments instead of 1.
- **Alternatives:** Single v1 launch at week 9-12

## 2026-04-18 — Architecture: Thin Harness / Fat Skills / Fat Code / Sealed Artifacts

- **Decision:** Four-layer decomposition across four repos (3 public, 1 private)
- **Reasoning:** Garry Tan's Thin Harness / Fat Skills pattern + Berkeley-exploit defense via Sealed Artifacts
- **ADR:** ADR-003

## 2026-04-18 — Judge panel: 3 judges (Sonnet 4.6 + Opus 4.7 + GPT-5.4)

- **Decision:** Majority vote with bootstrap CI; rubrics sealed and rotated quarterly
- **Reasoning:** Cross-vendor diversity reduces correlated failure; sealed rubrics resist Berkeley-style over-fitting
- **ADR:** ADR-002

## 2026-04-18 — Model routing: Opus for architecture, Sonnet for build, Haiku batch for fixtures

- **Decision:** Opus 4.7 for ADRs and rubric design; Sonnet 4.6 as Claude Code daily driver; Haiku 4.5 batch for all synthetic fixture generation
- **Reasoning:** Capability/cost optimization. ~$150-200 total build cost.

## 2026-04-18 — No monetization infrastructure

- **Decision:** Zero Stripe/billing tables/enterprise tier.
- **Reasoning:** Federal employee ethics rules. Prize money only.

## 2026-04-18 — Reproducibility baked in from day one

- **Decision:** Docker, pinned versions, deterministic seeds, public CI all present in Phase 0 scaffolding
- **Reasoning:** Retrofit cost >> build-in cost; AgentX judges weight reproducibility heavily
- **ADR:** ADR-004

---

## 2026-04-19 — Repos hosted under forgedynamicsai GitHub org

- **Decision:** Brain-Wrought repos live under github.com/forgedynamicsai, not a standalone brain-wrought org
- **Reasoning:** Practical — existing org, no new admin overhead. No commercial activity (no revenue, no marketing, no licensing) so ethics optics remain clean. "Independent benchmark" claim holds as long as Forge Dynamics doesn't commercialize Brain-Wrought.
- **Constraint added:** If Forge Dynamics ever takes outside revenue, Brain-Wrought must be transferred to a neutral org before any Forge Dynamics commercial announcement.

---

## 2026-04-19 — brain_wrought schema hosted in wroughtai Supabase project

- **Decision:** Use `brain_wrought` schema inside the `wroughtai` Supabase project (ref: `dtvdkuhteckxiwdjiikf`, US East) instead of a dedicated project
- **Reasoning:** Supabase free tier limits to 2 active projects per user; all slots occupied. `brain_wrought` schema is fully isolated from WroughtAI's `public` schema. RLS enabled independently.
- **Constraint:** WroughtAI migrations must stay in `public` schema. Brain-Wrought migrations use `brain_wrought` schema. No cross-schema queries.
- **Exit condition:** When a free slot opens, create a dedicated Supabase project, run `migrations/0001_initial.sql` against it, and drop `brain_wrought` schema from the wroughtai project.
- **Documented in:** `forgedynamicsai/wrought-ai/supabase/SHARED_SCHEMAS.md`

---

*(Append new decisions below. Never edit past entries — add a superseding entry if direction changes.)*
