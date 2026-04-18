"""brain-wrought CLI entry point."""
from __future__ import annotations

import hashlib
from typing import Annotated

import typer

from brain_wrought_harness.models import EvaluationConfig

app = typer.Typer(
    name="brain-wrought",
    help="Brain-Wrought personal-brain benchmark CLI.",
    no_args_is_help=True,
)


@app.command()
def self_eval(
    submission: str = typer.Option(..., help="Docker image tag for the submission"),
    fixtures: str = typer.Option("fixtures/clean/", help="Path to fixture directory"),
) -> None:
    """Run self-evaluation against public dev qrels."""
    typer.echo(f"Running self-eval for submission: {submission}")
    typer.echo(f"Fixtures: {fixtures}")
    typer.echo("Self-eval not yet implemented — coming in Phase 1 (BW-004).")


@app.command()
def submit(
    image: str = typer.Option(..., help="Docker image tag"),
    submission_yaml: str = typer.Option(..., help="Path to submission.yaml"),
) -> None:
    """Submit officially to Brain-Wrought leaderboard."""
    typer.echo("Official submission coming in Phase 4.")
    typer.echo(f"Image: {image}, config: {submission_yaml}")


@app.command()
def evaluate(
    docker_image: Annotated[str, typer.Argument(help="Docker image to evaluate")],
    seed: Annotated[int, typer.Option(help="Evaluation seed")] = 42,
    fixture_index: Annotated[int, typer.Option(help="Fixture index")] = 0,
    dry_run: Annotated[bool, typer.Option(help="Print config, skip Docker")] = False,
) -> None:
    """Evaluate a Docker image against a Brain-Wrought fixture."""
    submission_hash = hashlib.sha256(docker_image.encode()).hexdigest()
    config = EvaluationConfig(
        submission_hash=submission_hash,
        docker_image=docker_image,
        evaluation_seed=seed,
        fixture_index=fixture_index,
    )
    if dry_run:
        typer.echo(config.model_dump_json(indent=2))
        return
    typer.echo("[dry_run=False] Docker evaluation not yet implemented")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
