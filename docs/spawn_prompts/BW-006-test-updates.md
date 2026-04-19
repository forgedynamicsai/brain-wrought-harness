Fix BW-006 test failures that surfaced after BW-INTEG-1 merged.

Repo: brain-wrought-harness
Branch: issue/BW-006-naive-grep-baseline (already checked out, do not create new branch)
Model: Sonnet 4.6
Estimated: 15-30 minutes

Context:
BW-INTEG-1 merged to main added an empty-vault preflight check to
run_retrieval_axis. The tests in tests/reference_submissions/test_naive_grep.py
were written before this check existed and create a `vault_42/` subdirectory
inside tmp_path that's separate from where qrels.json is written, leaving
fixtures_dir itself (tmp_path) with no .md files. The preflight now correctly
rejects this.

Four failing tests:
- test_self_eval_docker_timeout
- test_self_eval_docker_success
- test_self_eval_malformed_output
- test_self_eval_runs_end_to_end

All four fail on the same RuntimeError from orchestration.py line 176.

REQUIRED CHANGES

1. For the three mocked tests (docker_timeout, docker_success, malformed_output):
   Remove the `vault = tmp_path / "vault_42"` and `vault.mkdir()` lines.
   Add a single dummy .md file creation before the run_retrieval_axis call:

       (tmp_path / "placeholder.md").write_text("placeholder")

   The mocked tests don't exercise real retrieval — they mock subprocess.Popen
   — so they just need the preflight check to pass. A single placeholder file
   satisfies that without affecting mock behavior.

2. For test_self_eval_runs_end_to_end:
   Remove the `vault = tmp_path / f"vault_{seed}"` + `vault.mkdir()` lines.
   Change the _make_vault call to use tmp_path directly instead of vault:

       _make_vault(tmp_path, {...})

   This matches the flat-vault contract that the fixture generator produces.

3. Verify the changes don't break the 7 currently-passing tests.
   Run: poetry run pytest tests/reference_submissions/test_naive_grep.py -v
   Expected: 11 passed, 1 skipped, 0 failed.

4. Also update test_scores_are_low (currently skipped with
   "reference_scores.json not yet populated") to a concrete expectation
   once the end-to-end test passes and produces real scores:

   - Run test_self_eval_runs_end_to_end (which now passes)
   - Capture the actual P@10, Recall@10, MRR, nDCG@10
   - Write those values to reference_submissions/naive_grep/reference_scores.json
     in the format the test expects
   - Remove the skip marker from test_scores_are_low
   - Expected P@10 in 0.15-0.35 range for this small vault

   If reference_scores.json already has a schema you can see from the test,
   match it exactly. If not, infer from the skip message and the test code.

OUT OF SCOPE

- Do not modify orchestration.py. BW-INTEG-1 logic is correct.
- Do not refactor the test helpers (_write_qrels, _make_vault, etc.) unless
  absolutely necessary for correctness.
- Do not change the naive_grep entrypoint.py. That was just refactored for
  BW-006 and works.

DELIVERABLE

Single commit on the existing BW-006 branch:
"fix(tests): BW-006 — update tests for BW-INTEG-1 flat-vault contract"

Do not open a new PR. PR #8 already tracks this branch. Push to origin.

Report:
- Commit SHA
- Final test count (expect 12 passed, 0 skipped, 0 failed)
- Actual reference scores written to reference_scores.json
