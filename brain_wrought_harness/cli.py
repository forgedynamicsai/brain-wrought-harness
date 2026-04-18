"""brain-wrought CLI entry point."""

import typer

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


if __name__ == "__main__":
    app()
