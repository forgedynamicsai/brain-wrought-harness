# brain-wrought-harness

The thin orchestration layer for the Brain-Wrought personal-brain benchmark.

## What this is

Brain-Wrought evaluates AI systems that read, maintain, and reason over personal knowledge vaults ("personal brains"). This repo contains:

- **`brain-wrought` CLI** — submit and self-evaluate
- **pytest-based runner** — orchestrates eval against submissions
- **Submission intake** — validates `submission.yaml`, triggers official eval
- **Supabase migrations** — schema for submissions, runs, scores, leaderboard

## What this is NOT

- Scoring logic lives in [`brain-wrought-engine`](https://github.com/forgedynamicsai/brain-wrought-engine)
- Skill files (fixture generation, rubric scaffolds) live in [`brain-wrought-skills`](https://github.com/forgedynamicsai/brain-wrought-skills)
- Sealed artifacts (qrels, gold graphs, actual judge rubrics) live in a private repo

## Quickstart

```bash
# Install
pip install brain-wrought

# Build your submission as a Docker image
docker build -t my-brain:v1 /path/to/your/submission

# Run self-eval against public dev qrels
brain-wrought self-eval --submission my-brain:v1

# Submit officially
brain-wrought submit --image my-brain:v1 --submission-yaml ./submission.yaml
```

See [SUBMISSION_PROTOCOL.md](https://github.com/forgedynamicsai/brain-wrought-skills/blob/main/SUBMISSION_PROTOCOL.md) for the full submission interface.

## Architecture

Brain-Wrought uses a four-repo decomposition:
- **harness** (this repo): thin orchestration, CLI, submission intake
- **engine** (public): deterministic scoring code
- **skills** (public): markdown skills + public rubric scaffolds + docs
- **sealed** (private): qrels, gold graphs, actual judge rubrics

See [ADR-001](https://github.com/forgedynamicsai/brain-wrought-skills/blob/main/adr/ADR-001-three-axis-framework.md) for the three-axis evaluation design.

## Reproducibility

Every submission runs in a Docker container with `--network none`. Seeds derive from submission hash. Full CI reproduces reference submissions on every commit.

See [REPRODUCIBILITY_SPEC.md](https://github.com/forgedynamicsai/brain-wrought-skills/blob/main/REPRODUCIBILITY_SPEC.md).

## License

MIT.

## Citation

If you use Brain-Wrought in academic work:

```bibtex
@misc{brain-wrought-2026,
  author = {Street, Arron},
  title  = {Brain-Wrought: A Three-Axis Benchmark for Personal AI Knowledge Systems},
  year   = 2026,
  url    = {https://github.com/forgedynamicsai/brain-wrought-harness}
}
```
