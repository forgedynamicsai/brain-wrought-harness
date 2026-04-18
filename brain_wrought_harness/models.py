"""Harness data contracts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationConfig(BaseModel):
    submission_hash: str
    docker_image: str
    harness_version: str = "0.1.0"
    evaluation_seed: int = 42
    fixture_index: int = 0
    model_config = {"frozen": True}


class AxisResult(BaseModel):
    axis: Literal["retrieval", "ingestion", "assistant"]
    score: float = Field(ge=0.0, le=1.0)
    detail: dict[str, object] = Field(default_factory=dict)
    model_config = {"frozen": True}


class EvaluationResult(BaseModel):
    submission_hash: str
    harness_version: str
    axis_results: list[AxisResult]
    composite_score: float = Field(ge=0.0, le=1.0)
    status: Literal["evaluated", "failed"]
    error: str | None = None
    model_config = {"frozen": True}
