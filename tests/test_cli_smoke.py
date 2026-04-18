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
