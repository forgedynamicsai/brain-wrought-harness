"""brain-wrought CLI entry point."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from brain_wrought_harness.hashing import (
    compute_submission_hash,
    get_harness_version,
    get_image_digest,
)
from brain_wrought_harness.models import AxisResult, EvaluationConfig, EvaluationResult

app = typer.Typer(
    name="brain-wrought",
    help="Brain-Wrought personal-brain benchmark CLI.",
    no_args_is_help=True,
)

_DOCKER_TIMEOUT = 3600


class OutputFormat(str, Enum):
    json = "json"
    human = "human"


def _resolve_digest(docker_image: str) -> str:
    """Return the image content digest; fall back to hashing the tag on failure."""
    try:
        return get_image_digest(docker_image)
    except Exception as exc:
        print(
            f"[brain-wrought] WARNING: could not get image digest ({exc}); "
            "falling back to tag hash — submission_hash may not be stable across pulls.",
            file=sys.stderr,
        )
        return docker_image


def _run_docker_eval(docker_image: str, payload: dict[str, object]) -> EvaluationResult:
    """Run the Docker container and parse its stdout as a list of AxisResults."""
    harness_version = get_harness_version()
    digest = _resolve_digest(docker_image)
    submission_hash = compute_submission_hash(digest, harness_version)

    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-i", docker_image],
            input=json.dumps(payload).encode(),
            capture_output=True,
            timeout=_DOCKER_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return EvaluationResult(
            submission_hash=submission_hash,
            harness_version=harness_version,
            status="failed",
            error=f"timeout after {_DOCKER_TIMEOUT}s",
            composite_score=0.0,
            axis_results=[],
        )

    if result.returncode != 0:
        return EvaluationResult(
            submission_hash=submission_hash,
            harness_version=harness_version,
            status="failed",
            error=result.stderr.decode()[:500],
            composite_score=0.0,
            axis_results=[],
        )

    try:
        raw_list = json.loads(result.stdout.decode())
    except json.JSONDecodeError:
        return EvaluationResult(
            submission_hash=submission_hash,
            harness_version=harness_version,
            status="failed",
            error=f"malformed JSON: {result.stdout.decode()[:200]}",
            composite_score=0.0,
            axis_results=[],
        )

    axis_results = [AxisResult.model_validate(item) for item in raw_list]
    composite_score = (
        sum(r.score for r in axis_results) / len(axis_results) if axis_results else 0.0
    )
    return EvaluationResult(
        submission_hash=submission_hash,
        harness_version=harness_version,
        status="evaluated",
        composite_score=composite_score,
        axis_results=axis_results,
    )


@app.command("self-eval")
def self_eval(
    submission: Annotated[str, typer.Option(help="Docker image tag for the submission")],
    fixtures: Annotated[str, typer.Option(help="Path to fixture directory")] = "fixtures/clean/",
    dry_run: Annotated[bool, typer.Option(help="Print config, skip Docker")] = False,
    output: Annotated[OutputFormat, typer.Option(help="Output format")] = OutputFormat.human,
) -> None:
    """Run self-evaluation against the public dev fixture set."""
    submission_hash = hashlib.sha256(submission.encode()).hexdigest()

    if dry_run:
        config = EvaluationConfig(
            submission_hash=submission_hash,
            docker_image=submission,
            fixture_index=0,
        )
        typer.echo(config.model_dump_json(indent=2))
        return

    payload: dict[str, object] = {
        "submission_hash": submission_hash,
        "fixtures_path": str(Path(fixtures)),
    }

    eval_result = _run_docker_eval(submission, payload)

    if output == OutputFormat.json:
        typer.echo(eval_result.model_dump_json(indent=2))
    else:
        typer.echo(f"status:          {eval_result.status}")
        typer.echo(f"composite_score: {eval_result.composite_score:.4f}")
        if eval_result.error:
            typer.echo(f"error:           {eval_result.error}")
        for ar in eval_result.axis_results:
            typer.echo(f"  {ar.axis}: {ar.score:.4f}")

    if eval_result.status == "failed":
        raise typer.Exit(code=1)


@app.command()
def submit() -> None:
    """Official leaderboard submission — coming in Phase 4."""
    typer.echo("Official submission coming in Phase 4. See SUBMISSION_PROTOCOL.md.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
