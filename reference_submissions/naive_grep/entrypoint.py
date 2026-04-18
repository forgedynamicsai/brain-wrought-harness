"""Naive grep baseline submission for Brain-Wrought retrieval axis.

Protocol: reads a single JSON request from stdin, writes a single JSON
response to stdout.  No LLM calls.  No embedding similarity.  Pure
token-frequency grep over vault note files using ripgrep.

Request (stdin):
    {"mode": "retrieve", "vault_path": "/vault", "query": "...", "k": 10}

Response (stdout):
    {"results": [{"note_id": "<stem>", "score": <int>}, ...],
     "abstained": <bool>, "elapsed_ms": <int>}
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


def _tokenize(query: str) -> list[str]:
    """Lowercase split; drop empty strings."""
    return [t for t in query.lower().split() if t]


def _grep_token_counts(token: str, vault_path: str) -> dict[str, int]:
    """Return {filepath: match_count} for a single token across the vault.

    Uses ripgrep --count so each file appears at most once per token call.
    Returns an empty dict if rg exits non-zero (no matches).
    """
    result = subprocess.run(
        [
            "rg",
            "--count",
            "--ignore-case",
            "--glob", "*.md",
            token,
            vault_path,
        ],
        capture_output=True,
        text=True,
    )
    counts: dict[str, int] = {}
    # rg --count output format: "filepath:N"
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        # Split on the LAST colon (paths on Windows can have drive letters, but
        # here we're in a Linux container so the last colon separates count).
        parts = line.rsplit(":", 1)
        if len(parts) == 2:
            filepath, count_str = parts
            try:
                counts[filepath] = int(count_str)
            except ValueError:
                continue
    return counts


def retrieve(vault_path: str, query: str, k: int) -> tuple[list[dict[str, object]], bool]:
    """Core retrieval logic.  Returns (ranked_results, abstained)."""
    tokens = _tokenize(query)
    if not tokens:
        return [], True

    # Accumulate per-file scores across all tokens
    file_scores: dict[str, int] = {}
    for token in tokens:
        for filepath, count in _grep_token_counts(token, vault_path).items():
            file_scores[filepath] = file_scores.get(filepath, 0) + count

    if not file_scores:
        return [], True

    # Sort: score descending, then filepath ascending for determinism
    ranked = sorted(file_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_k = ranked[:k]

    results = [
        {"note_id": Path(fp).stem, "score": score}
        for fp, score in top_k
    ]
    return results, False


def handle_request(request: dict[str, object]) -> dict[str, object]:
    """Dispatch a single request dict, return response dict."""
    vault_path = str(request.get("vault_path", "/vault"))
    query = str(request.get("query", ""))
    k = int(request.get("k", 10))  # type: ignore[call-overload]

    t0 = time.monotonic()
    results, abstained = retrieve(vault_path, query, k)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    return {
        "results": results,
        "abstained": abstained,
        "elapsed_ms": elapsed_ms,
    }


if __name__ == "__main__":
    raw = sys.stdin.read()
    try:
        request = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON input: {exc}"}))
        sys.exit(1)

    response = handle_request(request)
    print(json.dumps(response))
