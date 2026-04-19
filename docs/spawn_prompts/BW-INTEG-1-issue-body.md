Surfaced during manual BW-006 end-to-end test after BW-002c merged.

## Symptom

`brain-wrought self-eval` produces all-zero retrieval scores with abstention_precision=1.0 and zero errors, despite:
- qrel generator producing correct relevance judgments (verified post-BW-002c)
- naive-grep container returning correct results when tested directly
- Popen-based persistent pipe working correctly for sequential queries
- Request/response pydantic serialization handling Unicode correctly

## Root cause

In `brain_wrought_harness/orchestration.py run_retrieval_axis`:

```python
vault_path = fixtures_dir / f"vault_{qrel_set.seed}"
# ...
"-v", f"{vault_path}:/vault:ro",
```

The orchestration constructs the Docker volume source path as `fixtures_dir/vault_{seed}`, but the fixture generator (`brain_wrought_engine.fixtures.generator.generate_brain`) produces notes directly in `out_dir/brain_{seed}_{index}/` with qrels.json at the same level — not in a nested `vault_{seed}` subdirectory.

Docker silently creates empty bind mount sources, so the container starts successfully but sees an empty /vault. Grep finds zero files. All queries abstain. abstention_precision=1.0 because everything classifies as abstention.

## Fix

Change orchestration to mount fixtures_dir directly:

```python
vault_path = fixtures_dir  # notes and qrels.json are in the same directory
```

Update the docstring to reflect the corrected contract.

## Tests required

1. `test_vault_mount_matches_fixtures_dir`: call run_retrieval_axis with a fixtures_dir containing both qrels.json and .md files; verify retrieved note_ids are non-empty for at least one non-abstention query.
2. `test_empty_vault_raises_clear_error`: if fixtures_dir exists but has no .md files, the function should fail with a meaningful error message, not silently produce all-zero scores with abstention_precision=1.0.

## Priority

HIGH. Blocks Phase 1 public launch. Without this fix, no submission can produce non-zero retrieval scores via the CLI.
