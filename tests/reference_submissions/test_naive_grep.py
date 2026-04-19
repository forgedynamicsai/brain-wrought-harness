"""Tests for the naive grep reference submission (BW-006).

Docker-dependent tests are skipped when the docker binary is absent.
Non-Docker tests exercise entrypoint.py directly (subprocess Python call)
with a real or stub ripgrep.

After BW-004c, the harness drives containers via per-query JSON-line pipe.
The entrypoint reads one JSON line per query, writes one JSON line response,
and flushes; the harness closes stdin after the last query.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from brain_wrought_harness.orchestration import run_retrieval_axis

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
    """Run entrypoint.py via the current Python interpreter, return parsed stdout.

    Sends one JSON line (with vault_path injected) and reads the first response
    line back.  Matches the per-query line protocol used by the harness.
    """
    payload = dict(request_dict)
    payload["vault_path"] = vault_path
    result = subprocess.run(
        [sys.executable, str(_ENTRYPOINT)],
        input=(json.dumps(payload) + "\n").encode(),
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"entrypoint exited {result.returncode}: {result.stderr.decode()}"
    )
    first_line = result.stdout.decode().splitlines()[0]
    parsed: dict[str, Any] = json.loads(first_line)
    return parsed


def _make_vault(tmp_path: Path, notes: dict[str, str]) -> Path:
    """Create .md files in tmp_path; return the vault Path."""
    for stem, body in notes.items():
        (tmp_path / f"{stem}.md").write_text(body, encoding="utf-8")
    return tmp_path


def _write_qrels(fixtures_dir: Path, seed: int, entries: list[dict[str, object]]) -> None:
    """Write a minimal qrels.json to fixtures_dir."""
    qrels = {
        "qrel_version": "v1",
        "seed": seed,
        "entries": entries,
    }
    (fixtures_dir / "qrels.json").write_text(json.dumps(qrels), encoding="utf-8")


def _make_mock_proc(response_lines: list[str]) -> MagicMock:
    """Mock Popen that yields response_lines one per readline()."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.wait.return_value = 0
    line_iter = iter(response_lines)

    def _readline() -> str:
        try:
            return next(line_iter)
        except StopIteration:
            return ""

    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline = _readline
    return mock_proc


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
    vault_path = str(_make_vault(
        tmp_path,
        {
            "alice-chen": "Alice Chen is an engineer who works on Project Helios.",
            "bob-park": "Bob Park is a manager. He met with Alice Chen last week.",
            "project-helios": "Project Helios is the main initiative this quarter.",
        },
    ))
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

    for item in response["results"]:
        assert isinstance(item["note_id"], str)
        assert isinstance(item["score"], int)
        assert item["score"] >= 1

    # alice-chen mentions all 4 query tokens; must rank first.
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
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "anything at all", "k": 10},
        str(tmp_path),
    )
    assert response["abstained"] is True
    assert response["results"] == []


@_skip_no_rg
def test_entrypoint_abstains_on_no_matching_tokens(tmp_path: Path) -> None:
    """Vault with notes that contain no query tokens → abstained=true."""
    vault_path = str(_make_vault(
        tmp_path,
        {"note-a": "The quick brown fox jumps."},
    ))
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "xenotopia paradox engine zephyr ixion", "k": 10},
        vault_path,
    )
    assert response["abstained"] is True
    assert response["results"] == []


# ---------------------------------------------------------------------------
# 5. Harness integration: self-eval_docker_success
#    Mock Popen that responds with naive_grep-format retrieve responses.
# ---------------------------------------------------------------------------


def test_self_eval_docker_success(tmp_path: Path) -> None:
    """run_retrieval_axis produces scored AxisResult from naive_grep-format responses.

    naive_grep uses integer scores; harness must accept score: int in results.
    """
    vault = tmp_path / "vault_42"
    vault.mkdir()
    _write_qrels(
        tmp_path,
        seed=42,
        entries=[
            {
                "query_id": "q1",
                "query_text": "What did Alice work on?",
                "relevant_note_ids": ["alice-chen"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q2",
                "query_text": "Project Helios status?",
                "relevant_note_ids": ["project-helios"],
                "query_type": "factual",
                "expected_abstain": False,
            },
        ],
    )

    # naive_grep-style responses: integer scores, not floats
    responses = [
        json.dumps({"results": [{"note_id": "alice-chen", "score": 5}],
                    "abstained": False, "elapsed_ms": 12}) + "\n",
        json.dumps({"results": [{"note_id": "project-helios", "score": 3}],
                    "abstained": False, "elapsed_ms": 8}) + "\n",
    ]
    mock_proc = _make_mock_proc(responses)

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path,
            image_tag="naive-grep:v1",
            startup_timeout=5.0,
        )

    assert result.axis == "retrieval"
    assert 0.0 <= result.score <= 1.0
    assert result.detail["recall_at_k"] == pytest.approx(1.0)
    assert result.detail["error_count"] == 0
    assert result.detail["query_count"] == 2


# ---------------------------------------------------------------------------
# 6. Harness integration: self_eval_docker_timeout
#    Mock Popen that hangs on the second query; verify partial results returned.
# ---------------------------------------------------------------------------


def test_self_eval_docker_timeout(tmp_path: Path) -> None:
    """Query-level timeout kills container and marks remaining queries errored."""
    vault = tmp_path / "vault_42"
    vault.mkdir()
    _write_qrels(
        tmp_path,
        seed=42,
        entries=[
            {
                "query_id": "q1",
                "query_text": "Alice Chen projects?",
                "relevant_note_ids": ["alice-chen"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q2",
                "query_text": "Project Helios details?",
                "relevant_note_ids": ["project-helios"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q3",
                "query_text": "Bob Park responsibilities?",
                "relevant_note_ids": ["bob-park"],
                "query_type": "factual",
                "expected_abstain": False,
            },
        ],
    )

    first_response = (
        json.dumps({"results": [{"note_id": "alice-chen", "score": 3}],
                    "abstained": False, "elapsed_ms": 10}) + "\n"
    )
    block_event = threading.Event()
    call_count: list[int] = [0]

    def _readline_with_hang() -> str:
        call_count[0] += 1
        if call_count[0] == 1:
            return first_response
        block_event.wait(timeout=30)
        return ""

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline = _readline_with_hang
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.wait.return_value = 0

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path,
            image_tag="naive-grep:v1",
            query_timeout=0.05,
            startup_timeout=5.0,
        )

    block_event.set()
    mock_proc.kill.assert_called()
    assert result.detail["error_count"] >= 2


# ---------------------------------------------------------------------------
# 7. Harness integration: self_eval_malformed_output
#    Mock Popen that returns invalid JSON for first query; loop continues.
# ---------------------------------------------------------------------------


def test_self_eval_malformed_output(tmp_path: Path) -> None:
    """Malformed JSON response marks that query errored; scoring continues."""
    vault = tmp_path / "vault_42"
    vault.mkdir()
    _write_qrels(
        tmp_path,
        seed=42,
        entries=[
            {
                "query_id": "q1",
                "query_text": "Alice Chen projects?",
                "relevant_note_ids": ["alice-chen"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q2",
                "query_text": "Project Helios status?",
                "relevant_note_ids": ["project-helios"],
                "query_type": "factual",
                "expected_abstain": False,
            },
        ],
    )

    bad_line = "this is not json from naive-grep\n"
    good_line = (
        json.dumps({"results": [{"note_id": "project-helios", "score": 4}],
                    "abstained": False, "elapsed_ms": 9}) + "\n"
    )
    mock_proc = _make_mock_proc([bad_line, good_line])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path,
            image_tag="naive-grep:v1",
            startup_timeout=5.0,
        )

    assert result.detail["error_count"] == 1
    assert result.detail["query_count"] == 2
    # q2 scored: project-helios retrieved, recall = 1.0
    assert result.detail["recall_at_k"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 8. End-to-end self-eval against a real Docker container
# ---------------------------------------------------------------------------


@_skip_docker
def test_self_eval_runs_end_to_end(tmp_path: Path) -> None:
    """Full self-eval with real naive-grep container against a seeded vault.

    Builds the image (or reuses a cached build), creates a small fixture vault
    with qrels, and runs run_retrieval_axis end-to-end.  Asserts that scores
    are in [0, 1] and that all four retrieval metrics are present.

    P@10 should be > 0 for at least some queries since the vault contains
    the exact query terms.  It should be < 1.0 since k=10 with only a few
    relevant notes dilutes precision.
    """
    # Build the image
    build_result = subprocess.run(
        ["docker", "build", "-t", "naive-grep-test:bw006-e2e", str(_DOCKERFILE_DIR)],
        capture_output=True,
        timeout=300,
    )
    assert build_result.returncode == 0, (
        f"docker build failed:\n{build_result.stderr.decode()}"
    )

    # Create a small vault
    seed = 7
    vault = tmp_path / f"vault_{seed}"
    vault.mkdir()
    _make_vault(
        vault,
        {
            "alice-chen": (
                "Alice Chen is a senior engineer on Project Helios. "
                "She leads the backend architecture work."
            ),
            "bob-park": (
                "Bob Park is a product manager. He coordinates between "
                "Alice Chen and the design team."
            ),
            "project-helios": (
                "Project Helios is the main product initiative for 2026. "
                "Alice Chen owns the backend; Bob Park manages the roadmap."
            ),
            "meeting-jan-15": (
                "January 15 meeting: Alice Chen presented the Helios API design. "
                "Bob Park confirmed the roadmap priorities."
            ),
            "api-design": (
                "The Helios REST API uses JSON over HTTPS. "
                "All endpoints require authentication."
            ),
            "unrelated-note": (
                "The weather in Singapore is hot and humid year-round. "
                "Average temperature is 27 degrees Celsius."
            ),
        },
    )

    # Write qrels with a mix of answerable and abstention queries
    _write_qrels(
        tmp_path,
        seed=seed,
        entries=[
            {
                "query_id": "q1",
                "query_text": "What is Alice Chen working on?",
                "relevant_note_ids": ["alice-chen", "project-helios"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q2",
                "query_text": "What happened in the January meeting?",
                "relevant_note_ids": ["meeting-jan-15"],
                "query_type": "temporal",
                "expected_abstain": False,
            },
            {
                "query_id": "q3",
                "query_text": "Project Helios API design",
                "relevant_note_ids": ["api-design", "project-helios"],
                "query_type": "factual",
                "expected_abstain": False,
            },
            {
                "query_id": "q4",
                "query_text": "What is the Xenotopia Initiative?",
                "relevant_note_ids": [],
                "query_type": "abstention",
                "expected_abstain": True,
            },
        ],
    )

    result = run_retrieval_axis(
        fixtures_dir=tmp_path,
        image_tag="naive-grep-test:bw006-e2e",
        k=10,
        query_timeout=30.0,
        startup_timeout=60.0,
    )

    assert result.axis == "retrieval"
    assert 0.0 <= result.score <= 1.0
    assert result.detail["query_count"] == 4
    assert result.detail["error_count"] == 0

    # All four retrieval metrics present
    for metric in ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"):
        assert metric in result.detail, f"missing metric: {metric}"
        val = float(result.detail[metric])  # type: ignore[arg-type]
        assert 0.0 <= val <= 1.0, f"{metric} out of range: {val}"

    # Abstention tracked
    assert result.detail["abstention_total"] == 1

    # P@10 > 0: at least some relevant notes contain the query terms
    assert result.detail["precision_at_k"] > 0.0, (
        f"P@10 is 0 — naive_grep found nothing; check vault/qrel alignment. "
        f"Full detail: {result.detail}"
    )


# ---------------------------------------------------------------------------
# 9. Scores are low (sanity check on real Docker run)
# ---------------------------------------------------------------------------


@_skip_docker
def test_scores_are_low() -> None:
    """P@10 < 0.5 on the dev set — grep shouldn't magically be good.

    Reads reference_scores.json populated by the self-eval run.
    If the file has not been populated yet, this test is skipped.
    """
    scores_path = _DOCKERFILE_DIR / "reference_scores.json"
    data = json.loads(scores_path.read_text(encoding="utf-8"))
    if not data.get("_populated", False):
        pytest.skip("reference_scores.json not yet populated")

    p_at_10 = float(data["p_at_10"])
    assert p_at_10 < 0.5, (
        f"P@10={p_at_10:.4f} looks too high for naive grep — "
        "investigate qrel/vault alignment before accepting these scores."
    )
    assert p_at_10 > 0.0, (
        f"P@10={p_at_10:.4f} is zero — abstention handling may be broken."
    )


# ---------------------------------------------------------------------------
# 10. Determinism: same query+vault → same ranking
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_ranking_is_deterministic(tmp_path: Path) -> None:
    """Two calls with identical inputs produce identical ranked output."""
    vault_path = str(_make_vault(
        tmp_path,
        {
            "note-alpha": "Alice reviewed the quarterly budget proposal.",
            "note-beta": "Budget meeting notes. Alice and Bob attended.",
            "note-gamma": "Bob sent the quarterly report to Alice.",
        },
    ))
    request: dict[str, Any] = {"mode": "retrieve", "query": "Alice quarterly", "k": 5}
    r1 = _run_entrypoint(request, vault_path)
    r2 = _run_entrypoint(request, vault_path)
    assert r1["results"] == r2["results"]
    assert r1["abstained"] == r2["abstained"]


# ---------------------------------------------------------------------------
# 11. k is respected
# ---------------------------------------------------------------------------


@_skip_no_rg
def test_k_limit_respected(tmp_path: Path) -> None:
    """Results list is capped at k even when more notes match."""
    notes = {f"note-{i:03d}": f"Alice is mentioned here note {i}" for i in range(20)}
    vault_path = str(_make_vault(tmp_path, notes))
    response = _run_entrypoint(
        {"mode": "retrieve", "query": "Alice", "k": 5},
        vault_path,
    )
    assert len(response["results"]) <= 5
