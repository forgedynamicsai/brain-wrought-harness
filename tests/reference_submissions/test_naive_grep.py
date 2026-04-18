"""Tests for the naive grep reference submission (BW-006).

Docker-dependent tests are skipped when the docker binary is absent.
Non-Docker tests exercise entrypoint.py directly (subprocess Python call)
with a real or stub ripgrep.

Architectural note: the harness cli.py (BW-004b) sends a single JSON blob to
the container and expects aggregated AxisResults back.  The naive grep
entrypoint implements a per-query retrieval interface (mode=retrieve), which
is the correct per-spec design.  End-to-end self-eval requires the harness
to be updated to support per-query orchestration + metric computation. That
work is tracked separately; test_self_eval_runs_end_to_end is skipped until
both Docker and that harness update are in place.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_ENTRYPOINT = (
    Path(__file__).parent.parent.parent
    / "reference_submissions"
    / "naive_grep"
    / "entrypoint.py"
)
_DOCKERFILE_DIR = _ENTRYPOINT.parent

_DOCKER_AVAILABLE = shutil.which("docker") is not None
_RG_AVAILABLE = shutil.which("rg") is not None

_skip_docker = pytest.mark.skipif(
    not _DOCKER_AVAILABLE, reason="Docker binary not available in this environment"
)
_skip_no_rg = pytest.mark.skipif(
    not _RG_AVAILABLE, reason="ripgrep (rg) not available in this environment"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_entrypoint(request_dict: dict[str, Any], vault_path: str) -> dict[str, Any]:
    """Run entrypoint.py via the current Python interpreter, return parsed stdout."""
    payload = dict(request_dict)
    payload["vault_path"] = vault_path
    result = subprocess.run(
        [sys.executable, str(_ENTRYPOINT)],
        input=json.dumps(payload).encode(),
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"entrypoint exited {result.returncode}: {result.stderr.decode()}"
    )
    parsed: dict[str, Any] = json.loads(result.stdout.decode())
    return parsed


def _make_vault(tmp_path: Path, notes: dict[str, str]) -> str:
    """Create .md files in tmp_path; return path string."""
    for stem, body in notes.items():
        (tmp_path / f"{stem}.md").write_text(body, encoding="utf-8")
    return str(tmp_path)


# ---------------------------------------------------------------------------
# 1. Docker build
# ---------------------------------------------------------------------------


@_skip_docker
def test_dockerfile_builds() -> None:
    """docker build succeeds and exits zero."""
    result = subprocess.run(
        ["docker", "build", "-t", "naive-grep-test:bw006", str(_DOCKERFILE_DIR)],
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"docker build failed:\n{result.stderr.decode()}"
    )


# ---------------------------------------------------------------------------
# 2. Image size
# ---------------------------------------------------------------------------


@_skip_docker
def test_image_size_reasonable() -> None:
    """Built image is under 150 MB."""
    result = subprocess.run(
        [
            "docker", "image", "inspect",
            "--format", "{{.Size}}",
            "naive-grep-test:bw006",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "docker image inspect failed"
    size_bytes = int(result.stdout.strip())
    size_mb = size_bytes / (1024 * 1024)
    assert size_mb < 150, f"Image is {size_mb:.1f} MB; must be under 150 MB"


# ---------------------------------------------------------------------------
# 3. Entrypoint handles valid retrieve request
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_entrypoint_handles_valid_input(tmp_path: Path) -> None:
    """Feed a synthetic retrieve request; response has correct schema."""
    vault_path = _make_vault(
        tmp_path,
        {
            "alice-chen": "Alice Chen is an engineer who works on Project Helios.",
            "bob-park": "Bob Park is a manager. He met with Alice Chen last week.",
            "project-helios": "Project Helios is the main initiative this quarter.",
        },
    )
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "Alice Chen Project Helios", "k": 10},
        vault_path,
    )
    assert "results" in response, "response missing 'results' key"
    assert "abstained" in response, "response missing 'abstained' key"
    assert "elapsed_ms" in response, "response missing 'elapsed_ms' key"
    assert response["abstained"] is False
    assert isinstance(response["results"], list)
    assert len(response["results"]) > 0

    # Every result must have note_id (str) and score (int >= 1)
    for item in response["results"]:
        assert isinstance(item["note_id"], str)
        assert isinstance(item["score"], int)
        assert item["score"] >= 1

    # alice-chen mentions all 4 query tokens ("alice", "chen", "project", "helios")
    # while the other notes match only 2. It must rank first.
    note_ids = [r["note_id"] for r in response["results"]]
    assert note_ids[0] == "alice-chen", (
        f"alice-chen should be ranked first (matches all 4 tokens); got {note_ids}"
    )


# ---------------------------------------------------------------------------
# 4. Entrypoint abstains on empty vault
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_entrypoint_abstains_on_empty_vault(tmp_path: Path) -> None:
    """Empty vault → abstained=true, results=[]."""
    vault_path = str(tmp_path)  # no .md files
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "anything at all", "k": 10},
        vault_path,
    )
    assert response["abstained"] is True
    assert response["results"] == []


@_skip_no_rg
def test_entrypoint_abstains_on_no_matching_tokens(tmp_path: Path) -> None:
    """Vault with notes that contain no query tokens → abstained=true."""
    vault_path = _make_vault(
        tmp_path,
        {"note-a": "The quick brown fox jumps."},
    )
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "xenotopia paradox engine zephyr ixion", "k": 10},
        vault_path,
    )
    assert response["abstained"] is True
    assert response["results"] == []


# ---------------------------------------------------------------------------
# 5. End-to-end self-eval
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "Requires: (1) Docker installed, (2) harness CLI updated to support "
        "per-query orchestration and metric computation (current cli.py sends a "
        "single blob expecting AxisResults; naive grep implements the per-query "
        "mode=retrieve interface). Track in BW-006 follow-up."
    )
)
def test_self_eval_runs_end_to_end(tmp_path: Path) -> None:
    """Full self-eval against a seeded fixture vault produces retrieval scores."""
    # Not yet runnable — see skip reason above.


# ---------------------------------------------------------------------------
# 6. Scores are low (sanity check)
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason="Requires Docker and a running self-eval. See test_self_eval_runs_end_to_end."
)
def test_scores_are_low() -> None:
    """P@10 < 0.5 on the dev set — grep shouldn't magically be good."""
    # Not yet runnable.


# ---------------------------------------------------------------------------
# 7. Determinism: same query+vault → same ranking
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_ranking_is_deterministic(tmp_path: Path) -> None:
    """Two calls with identical inputs produce identical ranked output."""
    vault_path = _make_vault(
        tmp_path,
        {
            "note-alpha": "Alice reviewed the quarterly budget proposal.",
            "note-beta": "Budget meeting notes. Alice and Bob attended.",
            "note-gamma": "Bob sent the quarterly report to Alice.",
        },
    )
    request: dict[str, Any] = {"mode": "retrieve", "query": "Alice quarterly", "k": 5}
    r1 = _run_entrypoint(request, vault_path)
    r2 = _run_entrypoint(request, vault_path)
    assert r1["results"] == r2["results"]
    assert r1["abstained"] == r2["abstained"]


# ---------------------------------------------------------------------------
# 8. k is respected
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_k_limit_respected(tmp_path: Path) -> None:
    """Results list is capped at k even when more notes match."""
    notes = {f"note-{i:03d}": f"Alice is mentioned here note {i}" for i in range(20)}
    vault_path = _make_vault(tmp_path, notes)
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "Alice", "k": 5},
        vault_path,
    )
    assert len(response["results"]) <= 5
