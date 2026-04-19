# DECISIONS — brain-wrought-harness

Running log of meaningful harness-side choices. Append-only.

Format: date, decision, reasoning, alternative considered.

---

## 2026-04-19 — Engine as subdirectory, not symlink

- **Decision:** `brain-wrought-engine/` lives as `./engine/` subdirectory of harness repo, not a sibling symlink.
- **Reasoning:** Poetry path-dep could not resolve symlinks to sibling repos in CI; subdirectory layout works deterministically. `poetry.lock` records path as `./engine`.
- **Alternatives:** Symlink to sibling (broke in CI); PyPI publish (blocked on BW-PKG-1).
- **Tracked debt:** BW-PKG-1 — replace with PyPI publish before v1 public launch.

---

## 2026-04-19 — BW-006 naive-grep as reference submission pattern

- **Decision:** Reference submissions live under `reference_submissions/` as Dockerized offline-capable images, exercised end-to-end by the harness via `brain-wrought self-eval`.
- **Reasoning:** Proves the submission contract works; sets a scoring floor ("did you beat grep?"); matches SUBMISSION_PROTOCOL §3 exactly.
- **Phase 1 reference scores (seed=42, 50-note vault):** P@10 0.3214, Recall@10 0.9119, MRR 0.8595, nDCG@10 0.8101.
- **Alternatives considered:** Python-script-as-submission (rejected — no Docker isolation, no `--network none` enforcement).

---

## 2026-04-19 — BW-INTEG-1 vault mount path

- **Decision:** Harness mounts submission's brain at `/brain` inside the container (read/write for ingest mode; read-only for retrieve/assist).
- **Reasoning:** Matches SUBMISSION_PROTOCOL §2; mirrors SWE-bench container conventions; enables offline eval via `--network none`.

---

## 2026-04-18 — Typer over Click for CLI

- **Decision:** `brain-wrought` CLI built on Typer.
- **Reasoning:** Cleaner pydantic integration, better ergonomics for new projects. Documented in BW-004a spawn prompt.

---

## 2026-04-18 — Supabase `brain_wrought` schema with RLS

- **Decision:** Submission/run/score persistence via Supabase with RLS on all tables; anonymous read on submissions + leaderboard; service-role write.
- **Reasoning:** Reuses WealthAgent + Forge Dynamics deployment pattern; free-tier adequate for launch; RLS prevents authenticated-user-sidechannel exploits.
- **ADR:** extends ADR-003's sealed-artifact pattern (DB is source of truth for submission metadata; scores are computed inside harness CI and written via service role).

---

*(Append new decisions below. Never edit past entries — add a superseding entry if direction changes.)*
