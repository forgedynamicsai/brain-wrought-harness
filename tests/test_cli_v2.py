"""BW-004b: tests for the renamed self-eval command, Docker wiring, submit stub."""
from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from brain_wrought_harness.cli import app

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


def _valid_axis_results() -> list[dict[str, object]]:
    return [
        {"axis": "retrieval", "score": 0.8, "detail": {}},
        {"axis": "ingestion", "score": 0.6, "detail": {}},
        {"axis": "assistant", "score": 0.7, "detail": {}},
    ]


# ---------------------------------------------------------------------------
# Command existence / renaming
# ---------------------------------------------------------------------------


def test_self_eval_renamed() -> None:
    """'brain-wrought evaluate' no longer exists; 'brain-wrought self-eval' does."""
    result_old = runner.invoke(app, ["evaluate", "myimage:latest"])
    result_new = runner.invoke(app, ["self-eval", "--help"])
    assert result_old.exit_code != 0, "evaluate command should not exist"
    assert result_new.exit_code == 0, "self-eval command should exist"
    # Verify that the error for 'evaluate' is a "no such command" message
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
    """Dry-run behavior still works after rename (prints config JSON, exits 0)."""
    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir, "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "submission_hash" in result.output
    assert "docker_image" in result.output


# ---------------------------------------------------------------------------
# self-eval Docker success path
# ---------------------------------------------------------------------------


def test_self_eval_docker_success(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked subprocess returning valid JSON produces EvaluationResult."""
    fixtures_dir = str(tmp_path)
    axis_data = _valid_axis_results()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(axis_data).encode()
    mock_result.stderr = b""

    monkeypatch.setattr("brain_wrought_harness.cli.subprocess.run", lambda *a, **kw: mock_result)

    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir],
    )
    assert result.exit_code == 0, result.output
    assert "evaluated" in result.output or "composite_score" in result.output


def test_self_eval_docker_success_json_output(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--output json produces parseable JSON with status=evaluated."""
    fixtures_dir = str(tmp_path)
    axis_data = _valid_axis_results()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(axis_data).encode()
    mock_result.stderr = b""

    monkeypatch.setattr("brain_wrought_harness.cli.subprocess.run", lambda *a, **kw: mock_result)

    result = runner.invoke(
        app,
        [
            "self-eval",
            "--submission",
            "myimage:latest",
            "--fixtures",
            fixtures_dir,
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["status"] == "evaluated"
    assert len(parsed["axis_results"]) == 3
    # composite_score is mean of 0.8, 0.6, 0.7 = 0.7
    assert abs(parsed["composite_score"] - 0.7) < 1e-6


# ---------------------------------------------------------------------------
# self-eval Docker error paths
# ---------------------------------------------------------------------------


def test_self_eval_docker_timeout(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked subprocess timing out produces result with error='timeout after 3600s'."""
    fixtures_dir = str(tmp_path)

    def _raise_timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["docker"], timeout=3600)

    monkeypatch.setattr("brain_wrought_harness.cli.subprocess.run", _raise_timeout)

    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir],
    )
    assert result.exit_code == 1
    assert "timeout after 3600s" in result.output


def test_self_eval_docker_failure(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked subprocess exit 1 captures first 500 chars of stderr."""
    fixtures_dir = str(tmp_path)
    stderr_msg = "container failed with a descriptive error message"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = b""
    mock_result.stderr = stderr_msg.encode()

    monkeypatch.setattr("brain_wrought_harness.cli.subprocess.run", lambda *a, **kw: mock_result)

    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir],
    )
    assert result.exit_code == 1
    assert "failed" in result.output
    assert stderr_msg[:50] in result.output


def test_self_eval_malformed_output(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-JSON stdout produces clean error."""
    fixtures_dir = str(tmp_path)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b"this is not json at all"
    mock_result.stderr = b""

    monkeypatch.setattr("brain_wrought_harness.cli.subprocess.run", lambda *a, **kw: mock_result)

    result = runner.invoke(
        app,
        ["self-eval", "--submission", "myimage:latest", "--fixtures", fixtures_dir],
    )
    assert result.exit_code == 1
    assert "malformed JSON" in result.output


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


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
