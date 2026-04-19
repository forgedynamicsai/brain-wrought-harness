"""Pydantic v2 models for per-query retrieval orchestration (BW-004c).

These are harness-local mirrors of engine/protocol shapes so the harness
remains independent of engine model churn.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LocalQrelEntry(BaseModel):
    """Harness-local mirror of brain_wrought_engine.retrieval.models.QrelEntry."""

    query_id: str
    query_text: str
    relevant_note_ids: frozenset[str]
    query_type: Literal["factual", "temporal", "personalization", "abstention"]
    expected_abstain: bool = False

    model_config = {"frozen": True}


class LocalQrelSet(BaseModel):
    """Harness-local mirror of brain_wrought_engine.retrieval.models.QrelSet."""

    qrel_version: str = "v1"
    seed: int
    entries: tuple[LocalQrelEntry, ...]

    model_config = {"frozen": True}


class RetrieveRequest(BaseModel):
    """JSON line sent to the submission container (SUBMISSION_PROTOCOL.md §3)."""

    mode: Literal["retrieve"] = "retrieve"
    query: str
    k: int = Field(ge=1)

    model_config = {"frozen": True}


class RetrievedResult(BaseModel):
    """A single ranked result from the submission container."""

    note_id: str
    score: float

    model_config = {"frozen": True}


class RetrieveResponse(BaseModel):
    """JSON line received from the submission container for a retrieve request."""

    results: list[RetrievedResult]
    abstained: bool
    elapsed_ms: int

    model_config = {"frozen": True}
