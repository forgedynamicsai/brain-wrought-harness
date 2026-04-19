"""brain-wrought CLI entry point."""
from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from brain_wrought_harness.models import AxisResult, EvaluationConfig
from brain_wrought_harness.orchestration import run_retrieval_axis

app = typer.Typer(
    name="brain-wrought",
    help="Brain-Wrought personal-brain benchmark CLI.",
    no_args_is_help=True,
)


class OutputFormat(str, Enum):
    json = "json"
    human = "human"


@app.command("self-eval")
def self_eval(
    submission: Annotated[str, typer.Option(help="Docker image tag for the submission")],
    fixtures: Annotated[str, typer.Option(help="Path to fixture directory")] = "fixtures/clean/",
    dry_run: Annotated[bool, typer.Option(help="Print config, skip Docker")] = False,
    output: Annotated[OutputFormat, typer.Option(help="Output format")] = OutputFormat.human,
    query_timeout: Annotated[
        float, typer.Option(help="Per-query timeout in seconds")
    ] = 30.0,
    startup_timeout: Annotated[
        float, typer.Option(help="Container startup timeout in seconds")
    ] = 60.0,
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

    try:
        axis_result: AxisResult = run_retrieval_axis(
            fixtures_dir=Path(fixtures),
            image_tag=submission,
            query_timeout=query_timeout,
            startup_timeout=startup_timeout,
        )
    except RuntimeError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(code=1) from exc

    if output == OutputFormat.json:
        typer.echo(axis_result.model_dump_json(indent=2))
    else:
        detail = axis_result.detail
        typer.echo(f"axis:                 {axis_result.axis}")
        typer.echo(f"score:                {axis_result.score:.4f}")
        typer.echo(f"precision_at_k:       {detail.get('precision_at_k', 0.0):.4f}")
        typer.echo(f"recall_at_k:          {detail.get('recall_at_k', 0.0):.4f}")
        typer.echo(f"mrr:                  {detail.get('mrr', 0.0):.4f}")
        typer.echo(f"ndcg_at_k:            {detail.get('ndcg_at_k', 0.0):.4f}")
        typer.echo(f"abstention_precision: {detail.get('abstention_precision', 0.0):.4f}")
        typer.echo(f"queries:              {detail.get('query_count', 0)}")
        typer.echo(f"errors:               {detail.get('error_count', 0)}")


@app.command()
def submit() -> None:
    """Official leaderboard submission — coming in Phase 4."""
    typer.echo("Official submission coming in Phase 4. See SUBMISSION_PROTOCOL.md.")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
