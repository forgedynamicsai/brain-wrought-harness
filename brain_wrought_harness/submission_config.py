"""Submission configuration loaded from submission.yaml."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AxesConfig(BaseModel):
    retrieval: bool
    ingestion: bool
    assistant: bool
    model_config = {"frozen": True, "extra": "forbid"}


class SubmissionConfig(BaseModel):
    name: str
    team: str
    axes: AxesConfig
    models: list[str] = Field(min_length=1)
    paper_url: str | None = None
    resources: str | None = None
    license: str | None = None
    acknowledgments: str | None = None
    model_config = {"frozen": True, "extra": "forbid"}


def load_submission_config(path: Path) -> SubmissionConfig:
    """Load and validate submission.yaml. Raises ValueError with file+line context on failure."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: YAML parse error — {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a YAML mapping at top level")
    try:
        return SubmissionConfig.model_validate(raw)
    except Exception as exc:
        raise ValueError(f"{path}: {exc}") from exc
