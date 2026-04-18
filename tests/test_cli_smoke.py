"""Smoke tests for the Brain-Wrought CLI."""

from typer.testing import CliRunner

from brain_wrought_harness.cli import app

runner = CliRunner()


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_self_eval_help_exits_zero() -> None:
    result = runner.invoke(app, ["self-eval", "--help"])
    assert result.exit_code == 0


def test_self_eval_dry_run_smoke() -> None:
    """self-eval --dry-run prints config JSON and exits 0."""
    result = runner.invoke(
        app, ["self-eval", "--submission", "myimage:latest", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "submission_hash" in result.output or "docker_image" in result.output


def test_evaluate_command_removed() -> None:
    """The old 'evaluate' positional command no longer exists."""
    result = runner.invoke(app, ["evaluate", "myimage:latest"])
    assert result.exit_code != 0
