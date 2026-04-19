"""BW-004c: per-query orchestration loop tests.

All Docker subprocess calls are mocked so tests run without Docker.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brain_wrought_harness.orchestration import load_qrel_set, run_retrieval_axis
from brain_wrought_harness.orchestration_models import LocalQrelEntry, LocalQrelSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _qrel_entry(
    query_id: str,
    query_text: str,
    relevant_ids: frozenset[str],
    query_type: str = "factual",
    expected_abstain: bool = False,
) -> LocalQrelEntry:
    return LocalQrelEntry(
        query_id=query_id,
        query_text=query_text,
        relevant_note_ids=relevant_ids,
        query_type=query_type,  # type: ignore[arg-type]
        expected_abstain=expected_abstain,
    )


def _qrel_set(entries: list[LocalQrelEntry], seed: int = 42) -> LocalQrelSet:
    return LocalQrelSet(seed=seed, entries=tuple(entries))


def _response_line(
    results: list[dict[str, object]],
    abstained: bool = False,
    elapsed_ms: int = 10,
) -> str:
    return (
        json.dumps({"results": results, "abstained": abstained, "elapsed_ms": elapsed_ms})
        + "\n"
    )


def _write_qrels(fixtures_dir: Path, qrel_set: LocalQrelSet) -> None:
    qrels_path = fixtures_dir / "qrels.json"
    data: dict[str, object] = {
        "qrel_version": qrel_set.qrel_version,
        "seed": qrel_set.seed,
        "entries": [
            {
                "query_id": e.query_id,
                "query_text": e.query_text,
                "relevant_note_ids": list(e.relevant_note_ids),
                "query_type": e.query_type,
                "expected_abstain": e.expected_abstain,
            }
            for e in qrel_set.entries
        ],
    }
    qrels_path.write_text(json.dumps(data), encoding="utf-8")


def _make_mock_proc(response_lines: list[str]) -> MagicMock:
    """Return a mock Popen that yields *response_lines* one per readline() call."""
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
# 1. test_loads_qrelset_correctly
# ---------------------------------------------------------------------------


def test_loads_qrelset_correctly(tmp_path: Path) -> None:
    """load_qrel_set parses a valid qrels.json into LocalQrelSet."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a", "note-b"}))
    qset = _qrel_set([entry], seed=7)
    _write_qrels(tmp_path, qset)

    loaded = load_qrel_set(tmp_path)

    assert loaded.seed == 7
    assert len(loaded.entries) == 1
    assert loaded.entries[0].query_id == "q1"
    assert loaded.entries[0].relevant_note_ids == frozenset({"note-a", "note-b"})


# ---------------------------------------------------------------------------
# 2. test_single_query_roundtrip
# ---------------------------------------------------------------------------


def test_single_query_roundtrip(tmp_path: Path) -> None:
    """One query: request written, response parsed, score computed."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([{"note_id": "note-a", "score": 1.0}])
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.axis == "retrieval"
    assert result.detail["precision_at_k"] == pytest.approx(1.0 / 10)
    assert result.detail["recall_at_k"] == pytest.approx(1.0)
    assert result.detail["mrr"] == pytest.approx(1.0)
    assert result.detail["error_count"] == 0


# ---------------------------------------------------------------------------
# 3. test_multi_query_loop
# ---------------------------------------------------------------------------


def test_multi_query_loop(tmp_path: Path) -> None:
    """10 queries with perfect results each: aggregated means are all 1.0 / k."""
    entries = [
        _qrel_entry(f"q{i}", f"query {i}", frozenset({f"note-{i}"})) for i in range(10)
    ]
    qset = _qrel_set(entries)
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    k = 10
    responses = [
        _response_line([{"note_id": f"note-{i}", "score": 1.0}]) for i in range(10)
    ]
    mock_proc = _make_mock_proc(responses)

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", k=k, startup_timeout=5.0
        )

    assert result.detail["query_count"] == 10
    assert result.detail["error_count"] == 0
    assert result.detail["recall_at_k"] == pytest.approx(1.0)
    assert result.detail["mrr"] == pytest.approx(1.0)
    # P@k = 1/k for one relevant doc retrieved at rank 1
    assert result.detail["precision_at_k"] == pytest.approx(1.0 / k)
    assert result.detail["abstention_total"] == 0


# ---------------------------------------------------------------------------
# 4. test_abstention_correct_positive
# ---------------------------------------------------------------------------


def test_abstention_correct_positive(tmp_path: Path) -> None:
    """expected_abstain=True + submission abstains → abstention_precision = 1.0."""
    entry = _qrel_entry(
        "q1", "Who is Zyxel Brimhaven?", frozenset(), "abstention", expected_abstain=True
    )
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([], abstained=True)
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.detail["abstention_total"] == 1
    assert result.detail["abstention_correct"] == 1
    assert result.detail["abstention_precision"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 5. test_abstention_correct_negative
# ---------------------------------------------------------------------------


def test_abstention_correct_negative(tmp_path: Path) -> None:
    """expected_abstain=False + submission answers → normal scoring, abstention=0."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([{"note_id": "note-a", "score": 1.0}])
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.detail["abstention_total"] == 0
    assert result.detail["abstention_correct"] == 0
    assert result.detail["recall_at_k"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 6. test_abstention_false_positive
# ---------------------------------------------------------------------------


def test_abstention_false_positive(tmp_path: Path) -> None:
    """expected_abstain=False + submission abstains → recall=0 for that query."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([], abstained=True)
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.detail["recall_at_k"] == pytest.approx(0.0)
    assert result.detail["precision_at_k"] == pytest.approx(0.0)
    assert result.detail["mrr"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 7. test_abstention_false_negative
# ---------------------------------------------------------------------------


def test_abstention_false_negative(tmp_path: Path) -> None:
    """expected_abstain=True + submission doesn't abstain → incorrect non-abstention."""
    entry = _qrel_entry(
        "q1", "Who is Zyxel Brimhaven?", frozenset(), "abstention", expected_abstain=True
    )
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([{"note_id": "note-a", "score": 0.9}], abstained=False)
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.detail["abstention_total"] == 1
    assert result.detail["abstention_correct"] == 0
    assert result.detail["abstention_precision"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 8. test_query_timeout
# ---------------------------------------------------------------------------


def test_query_timeout(tmp_path: Path) -> None:
    """Query-level timeout kills container and returns partial results."""
    entries = [
        _qrel_entry(f"q{i}", f"query {i}", frozenset({f"note-{i}"})) for i in range(3)
    ]
    qset = _qrel_set(entries)
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    first_response = _response_line([{"note_id": "note-0", "score": 1.0}])

    # Second readline blocks until the test thread gives up (timeout fires).
    block_event = threading.Event()
    call_count: list[int] = [0]

    def _readline_with_hang() -> str:
        call_count[0] += 1
        if call_count[0] == 1:
            return first_response
        block_event.wait(timeout=30)  # blocks until test ends; daemon thread exits cleanly
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
            image_tag="test:latest",
            query_timeout=0.05,
            startup_timeout=5.0,
        )

    block_event.set()  # unblock hanging thread so it can exit

    assert result.detail["error_count"] >= 2  # at least the timed-out + remaining queries
    mock_proc.kill.assert_called()


# ---------------------------------------------------------------------------
# 9. test_startup_timeout
# ---------------------------------------------------------------------------


def test_startup_timeout(tmp_path: Path) -> None:
    """Startup timeout (first query) raises RuntimeError."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    block_event = threading.Event()

    def _blocking_readline() -> str:
        block_event.wait(timeout=30)
        return ""

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline = _blocking_readline
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.wait.return_value = 0

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="startup timeout"):
            run_retrieval_axis(
                fixtures_dir=tmp_path,
                image_tag="test:latest",
                startup_timeout=0.05,
            )

    block_event.set()
    mock_proc.kill.assert_called()


# ---------------------------------------------------------------------------
# 10. test_container_cleanup_on_success
# ---------------------------------------------------------------------------


def test_container_cleanup_on_success(tmp_path: Path) -> None:
    """On normal completion, stdin is closed and wait() is called."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line([{"note_id": "note-a", "score": 1.0}])
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    mock_proc.stdin.close.assert_called()
    mock_proc.wait.assert_called()


# ---------------------------------------------------------------------------
# 11. test_container_cleanup_on_exception
# ---------------------------------------------------------------------------


def test_container_cleanup_on_exception(tmp_path: Path) -> None:
    """Container is killed if orchestration raises (finally block runs)."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    block_event = threading.Event()

    def _blocking_readline() -> str:
        block_event.wait(timeout=30)
        return ""

    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline = _blocking_readline
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.wait.return_value = 0

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        with pytest.raises(RuntimeError):
            run_retrieval_axis(
                fixtures_dir=tmp_path,
                image_tag="test:latest",
                startup_timeout=0.05,
            )

    block_event.set()
    mock_proc.stdin.close.assert_called()


# ---------------------------------------------------------------------------
# 12. test_malformed_response_handled
# ---------------------------------------------------------------------------


def test_malformed_response_handled(tmp_path: Path) -> None:
    """Malformed JSON response marks that query as errored; loop continues."""
    entries = [
        _qrel_entry("q1", "query 1", frozenset({"note-1"})),
        _qrel_entry("q2", "query 2", frozenset({"note-2"})),
    ]
    qset = _qrel_set(entries)
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    bad_line = "this is not valid json\n"
    good_line = _response_line([{"note_id": "note-2", "score": 1.0}])
    mock_proc = _make_mock_proc([bad_line, good_line])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", startup_timeout=5.0
        )

    assert result.detail["error_count"] == 1
    assert result.detail["query_count"] == 2
    # Second query scored normally (recall=1.0 for one result)
    assert result.detail["recall_at_k"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 13. test_empty_qrelset
# ---------------------------------------------------------------------------


def test_empty_qrelset(tmp_path: Path) -> None:
    """Empty QrelSet returns zero-filled AxisResult without starting Docker."""
    qset = _qrel_set([])
    _write_qrels(tmp_path, qset)

    with patch("brain_wrought_harness.orchestration.subprocess.Popen") as mock_popen:
        result = run_retrieval_axis(fixtures_dir=tmp_path, image_tag="test:latest")

    mock_popen.assert_not_called()
    assert result.axis == "retrieval"
    assert result.score == pytest.approx(0.0)
    assert result.detail["query_count"] == 0
    assert result.detail["error_count"] == 0


# ---------------------------------------------------------------------------
# 14. test_all_four_metrics_computed
# ---------------------------------------------------------------------------


def test_all_four_metrics_computed(tmp_path: Path) -> None:
    """All four retrieval metrics (P@k, Recall@k, MRR, nDCG@k) present in AxisResult."""
    entry = _qrel_entry("q1", "What is X?", frozenset({"note-a", "note-b"}))
    qset = _qrel_set([entry])
    _write_qrels(tmp_path, qset)
    (tmp_path / f"vault_{qset.seed}").mkdir()

    response = _response_line(
        [
            {"note_id": "note-a", "score": 0.9},
            {"note_id": "note-c", "score": 0.5},
            {"note_id": "note-b", "score": 0.3},
        ]
    )
    mock_proc = _make_mock_proc([response])

    with patch("brain_wrought_harness.orchestration.subprocess.Popen", return_value=mock_proc):
        result = run_retrieval_axis(
            fixtures_dir=tmp_path, image_tag="test:latest", k=10, startup_timeout=5.0
        )

    detail = result.detail
    assert "precision_at_k" in detail
    assert "recall_at_k" in detail
    assert "mrr" in detail
    assert "ndcg_at_k" in detail

    # Spot-check: 2 relevant retrieved (note-a at rank 1, note-b at rank 3)
    assert detail["precision_at_k"] == pytest.approx(2 / 10)
    assert detail["recall_at_k"] == pytest.approx(1.0)
    assert detail["mrr"] == pytest.approx(1.0)
    assert float(detail["ndcg_at_k"]) > 0.0  # type: ignore[arg-type]
