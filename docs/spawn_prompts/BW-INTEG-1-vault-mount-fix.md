Fix BW-INTEG-1: orchestration vault-mount path mismatches fixture generator output.

Repo: brain-wrought-harness
Branch: issue/BW-INTEG-1-vault-mount-fix
Model: Sonnet 4.6
Estimated: 45-60 minutes

Full context in issue #15.

Summary of the bug:
In brain_wrought_harness/orchestration.py function run_retrieval_axis, the Docker
volume source path is constructed as:

    vault_path = fixtures_dir / f"vault_{qrel_set.seed}"

But the fixture generator (brain_wrought_engine.fixtures.generator.generate_brain)
produces notes directly in out_dir/brain_{seed}_{index}/ with qrels.json at the
same level — there is no nested vault_{seed} subdirectory.

Docker silently creates empty bind mount sources, so the container starts
successfully but sees an empty /vault. Grep finds zero .md files. Every query
returns empty results and classifies as abstention. Retrieval scores are all 0.0
and abstention_precision is 1.0 regardless of actual submission quality.

REQUIRED CHANGES

1. Fix the vault mount path in run_retrieval_axis:

   Replace:
       vault_path = fixtures_dir / f"vault_{qrel_set.seed}"
   With:
       vault_path = fixtures_dir

2. Update the run_retrieval_axis docstring:

   Old:
       fixtures_dir: Directory containing qrels.json and vault_{seed}/.
   New:
       fixtures_dir: Directory containing qrels.json and all .md note files
                     at the top level (the flat-vault structure produced by
                     brain_wrought_engine.fixtures.generator.generate_brain).

3. Add a preflight check that raises a clear error when the vault is empty.
   Before starting the Docker container, count the .md files in fixtures_dir.
   If zero .md files are present, raise RuntimeError with a message like:
       "no .md files found in fixtures_dir={fixtures_dir!r}; expected a
        flat vault directory with note files at the top level"
   This prevents silent all-zero scores in the future.

NEW TESTS REQUIRED

Add to tests/brain_wrought_harness/test_orchestration.py (or the equivalent
existing test file for orchestration):

1. test_vault_mount_matches_fixtures_dir:
   - Generate a real small vault via brain_wrought_engine.fixtures.generator.generate_brain
     with seed=42, note_count=20, use_llm=False.
   - Generate qrels for that vault via brain_wrought_engine.retrieval.qrel_generator.generate_qrels
     with seed=42, query_count=5.
   - Write qrels.json into the vault directory.
   - Call run_retrieval_axis with that directory as fixtures_dir and
     naive-grep:v1 as image_tag.
   - Assert the result's score field is > 0.0 (any non-zero proves notes
     were mounted and findable).
   - Assert at least one non-abstention query had a non-empty retrieved list
     (via instrumentation: patch precision_at_k and record calls, then assert
     at least one call had non-empty retrieved).

2. test_empty_vault_raises_clear_error:
   - Create a tmp directory with ONLY qrels.json (no .md files).
   - Call run_retrieval_axis with that directory.
   - Assert RuntimeError is raised with a message containing "no .md files".

Both tests require naive-grep:v1 Docker image to be built. If the image is
not present, the tests should skip with pytest.importorskip or a custom
skip marker — do NOT silently pass.

OUT OF SCOPE

- Do not change the fixture generator. The flat vault structure is correct.
- Do not change SUBMISSION_PROTOCOL.md. The submitter contract is unchanged.
- Do not touch the per-query scoring logic. That works correctly.
- Do not refactor the Popen setup or _read_line_timeout. Those are fine.

DELIVERABLE

Open a PR against main in brain-wrought-harness:
- Title: "[BW-INTEG-1] Fix orchestration vault mount path"
- Base: main
- Include reference scores in the PR description: after the fix, run
  brain-wrought self-eval --submission naive-grep:v1 --fixtures <fresh_vault>
  and paste the retrieval scores output. Expected P@10 in the 0.15-0.35 range
  (naive grep is a weak baseline by design).

Report:
- Commit SHA
- Test count (old + new)
- Actual axis A scores from naive-grep self-eval run against a fresh vault
- Any architectural concerns surfaced during the work

STOP conditions (do NOT proceed, report instead):
- If P@10 after fix is > 0.5: naive grep should not score that well; investigate
  whether qrels are over-generous or the fix introduced a different bug.
- If P@10 after fix is still 0.0: the vault mount path wasn't the only bug;
  investigate further and report findings without merging.
- If any pre-existing test fails that was passing before: the fix broke
  something; do not paper over it.
