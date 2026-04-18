# RISKS

Risk register. Sorted by severity × likelihood. Update when new risks surface or existing ones change.

Severity: 1 (nuisance) to 5 (project-killing).
Likelihood: 1 (unlikely) to 5 (near-certain).

---

## R-01: Competitor ships personal-brain eval first

- **Severity:** 4 — significant erosion of novelty claim
- **Likelihood:** 3
- **Mitigation:** Ship retrieval axis in 2 weeks (week of May 2). Flag planted publicly early.
- **Contingency:** Pivot positioning to "axis-complete, sealed-qrels alternative"

## R-02: Sealed qrels leak

- **Severity:** 5 — benchmark integrity collapses
- **Likelihood:** 2
- **Mitigation:** 2FA on GitHub; branch protection; minimal CI token scope; rotate qrels every 6 months
- **Contingency:** See `SECURITY.md` response protocol

## R-03: PCS disruption (September 2026)

- **Severity:** 3 — if v1 ships on time, PCS is not a blocker
- **Likelihood:** 5
- **Mitigation:** v1 ships June 20, 2026 — full 2+ months before PCS.

## R-04: Foreign Service ethics concern

- **Severity:** 4 — could require pausing
- **Likelihood:** 2
- **Mitigation:** Brain-Wrought is unpaid open-source. Confirm with Post Ethics Counselor before public launch.
- **Action:** Schedule Ethics Counselor check-in by week 6

## R-05: Judge panel cost explosion

- **Severity:** 2
- **Likelihood:** 2
- **Mitigation:** Aggressive caching on rubrics. Cap panel at 3 judges. Monitor weekly.

## R-06: Judge inter-rater agreement low

- **Severity:** 3
- **Likelihood:** 2
- **Mitigation:** Red-team rubrics before sealing; pilot with 20 tasks.

## R-07: Prompt injection succeeds against judges

- **Severity:** 4
- **Likelihood:** 3
- **Mitigation:** Adversarial injection suite tested during rubric design. Panel voting catches single-judge injection.

## R-08: Garry Tan or Berkeley RDI builds competing framework

- **Severity:** 3
- **Likelihood:** 3
- **Mitigation:** DM Garry Tan in Phase 0 offering collaboration/cross-linking.

## R-09: Arron burnout / overcommitment

- **Severity:** 4
- **Likelihood:** 3
- **Mitigation:** Forge Dynamics paused. 8-10 hrs/week sustainable pace.
- **Contingency:** Cut scope to retrieval-only v1 and ship that as AgentX submission.

## R-10: Reproducibility audit fails on a top-5 submission

- **Severity:** 3
- **Likelihood:** 2
- **Mitigation:** Reproducibility spec is precise and published. CI continuously validates reference submissions.

## R-11: Anthropic or OpenAI deprecates a judge model mid-cycle

- **Severity:** 2
- **Likelihood:** 3
- **Mitigation:** Snapshot IDs pinned; fallback judges identified (Gemini 3.1 Pro for GPT-5.4 slot)

---

*(Add new risks below as they surface. Review weekly.)*
