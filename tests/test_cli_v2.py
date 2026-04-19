"""BW-004b/BW-004c: tests for self-eval command, orchestration wiring, submit stub."""
from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from brain_wrought_harness.cli import app
from brain_wrought_harness.models import AxisResult

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fixtures_dir(tmp_path: Any) -> Any:
    """Return a temporary directory path string."""
    d = tmp_path / "fixtures"
    d.mkdir()
    return str(d)


def _ok_axis_result() -> AxisResult:
    return AxisResult(
        axis="retrieval",
        score=0.75,
        detail={
            "precision_at_k": 0.8,
            "recall_at_k": 0.6,
            "mrr": 0.9,
            "ndcg_at_k": 0.7,
            "abstention_precision": 1.0,
            "abstention_total": 2,
            "abstention_correct": 2,
            "query_count": 10,
            "error_count": 0,
            "k": 10,
        },
    )


# ---------------------------------------------------------------------------
# Command existence / renaming
# ---------------------------------------------------------------------------


def test_self_eval_renamed() -> None:
    """'brain-wrought evaluate' no longer exists; 'brain-wrought self-eval' does."""
    result_old = runner.invoke(app, ["evaluate", "myimage:latest"])
    result_new = runner.invoke(app, ["self-eval", "--help"])
    assert result_old.exit_code != 0, "evaluate command should not exist"
    assert result_new.exit_code == 0, "self-eval command should exist"
    assert "evaluate" in result_old.output or "No such command" in result_old.output


def test_submit_stub() -> None:
    """'brain-wrought submit' prints stub message and exits 1."""
    result = runner.invoke(app, ["submit"])
    assert result.exit_code == 1
    assert "Phase 4" in result.output
    assert "SUBMISSION_PROTOCOL.md" in result.output


# ---------------------------------------------------------------------------
# self-eval dry-run
# ---------------------------------------------------------------------------


def test_self_eval_dry_run(fixtures_dir: str) -> None:
    """Dry-run behavior still works (prints config JSON, exits 0)."""
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir, "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "submission_hash" in result.output
    assert "docker_image" in result.output


# ---------------------------------------------------------------------------
# self-eval orchestration success paths
# ---------------------------------------------------------------------------


def test_self_eval_docker_success(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked orchestration returning AxisResult produces human-readable output."""
    monkeypatch.setattr(
        "brain_wrought_harness.cli.run_retrieval_axis",
        lambda **kw: _ok_axis_result(),
    )
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "retrieval" in result.output
    assert "score" in result.output


def test_self_eval_docker_success_json_output(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output json produces parseable JSON with axis=retrieval and score."""
    monkeypatch.setattr(
        "brain_wrought_harness.cli.run_retrieval_axis",
        lambda **kw: _ok_axis_result(),
    )
    result = runner.invoke(
        app,
        [
            "self-eval",
            "--submission",
            "myimage:latest",
            "--fixtures",
            str(tmp_path),
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["axis"] == "retrieval"
    assert abs(parsed["score"] - 0.75) < 1e-6


def test_self_eval_docker_timeout(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestration RuntimeError (startup timeout) exits 1 and prints the message."""

    def _raise(**kw: object) -> AxisResult:
        raise RuntimeError("container did not respond within 60s startup timeout")

    monkeypatch.setattr("brain_wrought_harness.cli.run_retrieval_axis", _raise)
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "startup timeout" in result.output


def test_self_eval_docker_failure(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orchestration RuntimeError (container start failed) exits 1 and prints error."""

    def _raise(**kw: object) -> AxisResult:
        raise RuntimeError("failed to start container 'myimage:latest': No such file")

    monkeypatch.setattr("brain_wrought_harness.cli.run_retrieval_axis", _raise)
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "error" in result.output.lower()


def test_self_eval_malformed_output(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Partial results with errors are returned without crashing (exit 0)."""
    partial = AxisResult(
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
            "query_count": 5,
            "error_count": 5,
            "k": 10,
        },
    )
    monkeypatch.setattr(
        "brain_wrought_harness.cli.run_retrieval_axis",
        lambda **kw: partial,
    )
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "retrieval" in result.output


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def test_get_harness_version_non_empty() -> None:
    """get_harness_version returns a non-empty string (importlib.metadata path)."""
    from brain_wrought_harness.hashing import get_harness_version

    v = get_harness_version()
    assert isinstance(v, str)
    assert len(v) > 0


def test_submission_hash_deterministic() -> None:
    """compute_submission_hash with same inputs always returns same hash."""
    from brain_wrought_harness.hashing import compute_submission_hash

    h1 = compute_submission_hash("sha256:abc123", "0.1.0")
    h2 = compute_submission_hash("sha256:abc123", "0.1.0")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest length


def test_submission_hash_different_inputs() -> None:
    """Different inputs produce different hashes."""
    from brain_wrought_harness.hashing import compute_submission_hash

    h1 = compute_submission_hash("sha256:abc123", "0.1.0")
    h2 = compute_submission_hash("sha256:abc123", "0.2.0")
    h3 = compute_submission_hash("sha256:def456", "0.1.0")
    assert h1 != h2
    assert h1 != h3


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def test_yaml_loading_valid(tmp_path: Any) -> None:
    """Valid submission.yaml loads cleanly."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        """
name: My Brain System
team: Brain Team
axes:
  retrieval: true
  ingestion: false
  assistant: true
models:
  - claude-sonnet-4-6
""",
        encoding="utf-8",
    )
    config = load_submission_config(yaml_path)
    assert config.name == "My Brain System"
    assert config.team == "Brain Team"
    assert config.axes.retrieval is True
    assert config.axes.ingestion is False
    assert config.axes.assistant is True
    assert config.models == ["claude-sonnet-4-6"]
    assert config.paper_url is None


def test_yaml_loading_all_optional_fields(tmp_path: Any) -> None:
    """Valid submission.yaml with all optional fields loads cleanly."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        """
name: Full System
team: Full Team
axes:
  retrieval: true
  ingestion: true
  assistant: true
models:
  - model-a
  - model-b
paper_url: https://arxiv.org/abs/2026.00001
resources: "2x A100, 64GB RAM"
license: MIT
acknowledgments: "Thanks to the community"
""",
        encoding="utf-8",
    )
    config = load_submission_config(yaml_path)
    assert config.paper_url == "https://arxiv.org/abs/2026.00001"
    assert config.license == "MIT"
    assert len(config.models) == 2


def test_yaml_unknown_field(tmp_path: Any) -> None:
    """Unknown field raises ValueError containing the field name."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        """
name: My Brain System
team: Brain Team
axes:
  retrieval: true
  ingestion: false
  assistant: true
models:
  - my-model
unknown_field: should_cause_error
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown_field"):
        load_submission_config(yaml_path)


def test_yaml_missing_required(tmp_path: Any) -> None:
    """Missing required field raises ValueError containing the field name."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        """
name: My Brain System
axes:
  retrieval: true
  ingestion: false
  assistant: true
models:
  - my-model
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="team"):
        load_submission_config(yaml_path)


def test_yaml_empty_models_list(tmp_path: Any) -> None:
    """Empty models list raises ValueError."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        """
name: My Brain System
team: Brain Team
axes:
  retrieval: true
  ingestion: false
  assistant: true
models: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_submission_config(yaml_path)


def test_yaml_parse_error(tmp_path: Any) -> None:
    """Invalid YAML syntax raises ValueError with parse error context."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text("key: [unclosed bracket", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML parse error"):
        load_submission_config(yaml_path)


def test_yaml_not_a_mapping(tmp_path: Any) -> None:
    """YAML that is not a mapping raises ValueError."""
    from brain_wrought_harness.submission_config import load_submission_config

    yaml_path = tmp_path / "submission.yaml"
    yaml_path.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected a YAML mapping"):
        load_submission_config(yaml_path)
