"""Per-query retrieval orchestration loop (BW-004c).

Drives the submission Docker container through one JSON-line per query
(SUBMISSION_PROTOCOL.md §3, mode="retrieve") and aggregates per-query
scores into an AxisResult.

Container lifecycle:
  start  → write query line → read response line (repeat) → cleanup
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO

from brain_wrought_engine.retrieval.scorer import (
    mrr as _score_mrr,
)
from brain_wrought_engine.retrieval.scorer import (
    ndcg_at_k as _score_ndcg_at_k,
)
from brain_wrought_engine.retrieval.scorer import (
    precision_at_k as _score_precision_at_k,
)
from brain_wrought_engine.retrieval.scorer import (
    recall_at_k as _score_recall_at_k,
)

from brain_wrought_harness.models import AxisResult
from brain_wrought_harness.orchestration_models import (
    LocalQrelSet,
    RetrieveRequest,
    RetrieveResponse,
)

_DEFAULT_K = 10
_CLEANUP_WAIT_S = 10
_CLEANUP_TERM_S = 5


def load_qrel_set(fixtures_dir: Path) -> LocalQrelSet:
    """Parse qrels.json from *fixtures_dir* into a LocalQrelSet.

    Raises:
        RuntimeError: If the file is missing, unreadable, or structurally invalid.
    """
    qrels_path = fixtures_dir / "qrels.json"
    try:
        raw = qrels_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"cannot read {qrels_path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {qrels_path}: {exc}") from exc

    try:
        return LocalQrelSet.model_validate(data)
    except Exception as exc:
        raise RuntimeError(f"invalid QrelSet structure in {qrels_path}: {exc}") from exc


def _read_line_timeout(stream: IO[str], timeout: float) -> str | None:
    """Read one text line from *stream* with a wall-clock *timeout*.

    Returns the line string (including trailing newline) on success,
    or None if the timeout expires before a line arrives.
    """
    lines: list[str] = []

    def _reader() -> None:
        try:
            lines.append(stream.readline())
        except Exception:
            pass

    thread = threading.Thread(target=_reader, daemon=True)
    thread.start()
    thread.join(timeout)
    return lines[0] if lines else None


def _cleanup_container(
    proc: subprocess.Popen[str],
    stderr_lines: list[str],
) -> None:
    """Gracefully shut down *proc* and collect remaining stderr.

    Sequence: close stdin → wait 10 s → SIGTERM → wait 5 s → SIGKILL.
    Appends captured stderr lines to *stderr_lines* and prints them.
    """
    try:
        if proc.stdin is not None:
            proc.stdin.close()
    except Exception:
        pass

    try:
        proc.wait(timeout=_CLEANUP_WAIT_S)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=_CLEANUP_TERM_S)
        except subprocess.TimeoutExpired:
            proc.kill()

    if proc.stderr is not None:
        try:
            remaining = proc.stderr.read()
            if remaining:
                stderr_lines.extend(remaining.splitlines())
        except Exception:
            pass

    if stderr_lines:
        print("[brain-wrought] container stderr:", file=sys.stderr)
        for line in stderr_lines:
            print(f"  {line}", file=sys.stderr)


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def run_retrieval_axis(
    *,
    fixtures_dir: Path,
    image_tag: str,
    k: int = _DEFAULT_K,
    query_timeout: float = 30.0,
    startup_timeout: float = 60.0,
) -> AxisResult:
    """Drive the submission container through the per-query retrieval protocol.

    Loads QrelSet from *fixtures_dir*/qrels.json, starts the container with
    the vault mounted read-only, sends one retrieve request per QrelEntry,
    and aggregates results into an AxisResult.

    Abstention handling:
      - expected_abstain=True  + abstained=True  → correct abstention (counted separately)
      - expected_abstain=True  + abstained=False → incorrect non-abstention (counted separately)
      - expected_abstain=False + abstained=True  → treated as retrieved=() (recall=0)
      - expected_abstain=False + abstained=False → normal scoring path

    Args:
        fixtures_dir: Directory containing qrels.json and vault_{seed}/.
        image_tag: Docker image tag for the submission container.
        k: Number of results to request per query (default 10).
        query_timeout: Per-query response timeout in seconds (default 30).
        startup_timeout: Timeout for the first response, covering container
                         startup plus first query processing (default 60).

    Returns:
        AxisResult with axis="retrieval", score in [0, 1], and a detail dict
        containing per-metric means plus abstention stats and error count.

    Raises:
        RuntimeError: If qrels.json is unreadable, the container fails to
                      start, or the startup timeout fires with no response.
    """
    qrel_set = load_qrel_set(fixtures_dir)

    if not qrel_set.entries:
        return _zero_axis_result(k=k)

    vault_path = fixtures_dir / f"vault_{qrel_set.seed}"

    try:
        proc: subprocess.Popen[str] = subprocess.Popen(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "--network",
                "none",
                "-v",
                f"{vault_path}:/vault:ro",
                image_tag,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise RuntimeError(f"failed to start container {image_tag!r}: {exc}") from exc

    p_scores: list[float] = []
    r_scores: list[float] = []
    mrr_scores: list[float] = []
    ndcg_scores: list[float] = []

    abstention_total = 0
    abstention_correct = 0
    error_count = 0
    stderr_lines: list[str] = []

    try:
        for i, entry in enumerate(qrel_set.entries):
            request = RetrieveRequest(mode="retrieve", query=entry.query_text, k=k)

            try:
                if proc.stdin is None:
                    raise RuntimeError("container stdin is None")
                proc.stdin.write(request.model_dump_json() + "\n")
                proc.stdin.flush()
            except OSError as exc:
                raise RuntimeError(
                    f"failed to write query {entry.query_id!r} to stdin: {exc}"
                ) from exc

            effective_timeout = startup_timeout if i == 0 else query_timeout

            if proc.stdout is None:
                raise RuntimeError("container stdout is None")

            raw_line = _read_line_timeout(proc.stdout, effective_timeout)

            if raw_line is None:
                if i == 0:
                    proc.kill()
                    raise RuntimeError(
                        f"container {image_tag!r} did not respond within "
                        f"{startup_timeout}s startup timeout"
                    )
                # Query-level timeout: kill and return partial results.
                proc.kill()
                error_count += len(qrel_set.entries) - i
                break

            if not raw_line.strip():
                error_count += 1
                continue

            try:
                response = RetrieveResponse.model_validate_json(raw_line.strip())
            except Exception as exc:
                print(
                    f"[brain-wrought] malformed response for query "
                    f"{entry.query_id!r}: {exc}",
                    file=sys.stderr,
                )
                error_count += 1
                continue

            if entry.expected_abstain:
                abstention_total += 1
                if response.abstained:
                    abstention_correct += 1
            else:
                retrieved: tuple[str, ...] = (
                    ()
                    if response.abstained
                    else tuple(r.note_id for r in response.results)
                )
                relevant = entry.relevant_note_ids
                p_scores.append(_score_precision_at_k(relevant, retrieved, k))
                r_scores.append(_score_recall_at_k(relevant, retrieved, k))
                mrr_scores.append(_score_mrr(relevant, retrieved))
                ndcg_scores.append(_score_ndcg_at_k(relevant, retrieved, k))

    finally:
        _cleanup_container(proc, stderr_lines)

    return _aggregate(
        p_scores=p_scores,
        r_scores=r_scores,
        mrr_scores=mrr_scores,
        ndcg_scores=ndcg_scores,
        abstention_total=abstention_total,
        abstention_correct=abstention_correct,
        query_count=len(qrel_set.entries),
        error_count=error_count,
        k=k,
    )


def _zero_axis_result(k: int) -> AxisResult:
    return AxisResult(
        axis="retrieval",
        score=0.0,
        detail={
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr": 0.0,
            "ndcg_at_k": 0.0,
            "abstention_precision": 0.0,
            "abstention_total": 0,
            "abstention_correct": 0,
            "query_count": 0,
            "error_count": 0,
            "k": k,
        },
    )


def _aggregate(
    *,
    p_scores: list[float],
    r_scores: list[float],
    mrr_scores: list[float],
    ndcg_scores: list[float],
    abstention_total: int,
    abstention_correct: int,
    query_count: int,
    error_count: int,
    k: int,
) -> AxisResult:
    p_mean = _mean(p_scores)
    r_mean = _mean(r_scores)
    mrr_mean = _mean(mrr_scores)
    ndcg_mean = _mean(ndcg_scores)
    abstention_precision = (
        abstention_correct / abstention_total if abstention_total > 0 else 0.0
    )
    n = len(p_scores)
    score = (p_mean + r_mean + mrr_mean + ndcg_mean) / 4.0 if n > 0 else 0.0

    return AxisResult(
        axis="retrieval",
        score=score,
        detail={
            "precision_at_k": p_mean,
            "recall_at_k": r_mean,
            "mrr": mrr_mean,
            "ndcg_at_k": ndcg_mean,
            "abstention_precision": abstention_precision,
            "abstention_total": abstention_total,
            "abstention_correct": abstention_correct,
            "query_count": query_count,
            "error_count": error_count,
            "k": k,
        },
    )
