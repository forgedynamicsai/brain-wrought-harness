"""Focused unit tests for SubmissionConfig and AxesConfig validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from brain_wrought_harness.submission_config import (
    AxesConfig,
    SubmissionConfig,
    load_submission_config,
)

# ---------------------------------------------------------------------------
# AxesConfig
# ---------------------------------------------------------------------------


def test_axes_config_all_true() -> None:
    cfg = AxesConfig(retrieval=True, ingestion=True, assistant=True)
    assert cfg.retrieval is True
    assert cfg.ingestion is True
    assert cfg.assistant is True


def test_axes_config_mixed() -> None:
    cfg = AxesConfig(retrieval=True, ingestion=False, assistant=True)
    assert cfg.ingestion is False


def test_axes_config_frozen() -> None:
    cfg = AxesConfig(retrieval=True, ingestion=True, assistant=True)
    with pytest.raises(Exception):
        cfg.retrieval = False  # type: ignore[misc]


def test_axes_config_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        AxesConfig(retrieval=True, ingestion=True, assistant=True, extra="bad")  # type: ignore[call-arg]


def test_axes_config_missing_field_rejected() -> None:
    with pytest.raises(Exception):
        AxesConfig(retrieval=True, ingestion=True)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SubmissionConfig direct construction
# ---------------------------------------------------------------------------


def _minimal_axes() -> AxesConfig:
    return AxesConfig(retrieval=True, ingestion=False, assistant=True)


def test_submission_config_minimal() -> None:
    cfg = SubmissionConfig(
        name="Test System",
        team="Test Team",
        axes=_minimal_axes(),
        models=["model-a"],
    )
    assert cfg.name == "Test System"
    assert cfg.paper_url is None
    assert cfg.resources is None
    assert cfg.license is None
    assert cfg.acknowledgments is None


def test_submission_config_frozen() -> None:
    cfg = SubmissionConfig(
        name="Test System",
        team="Test Team",
        axes=_minimal_axes(),
        models=["model-a"],
    )
    with pytest.raises(Exception):
        cfg.name = "Other"  # type: ignore[misc]


def test_submission_config_extra_field_rejected() -> None:
    with pytest.raises(Exception):
        SubmissionConfig(  # type: ignore[call-arg]
            name="Test System",
            team="Test Team",
            axes=_minimal_axes(),
            models=["model-a"],
            unknown_field="bad",
        )


def test_submission_config_empty_models_rejected() -> None:
    with pytest.raises(Exception):
        SubmissionConfig(
            name="Test System",
            team="Test Team",
            axes=_minimal_axes(),
            models=[],
        )


def test_submission_config_multiple_models() -> None:
    cfg = SubmissionConfig(
        name="Test System",
        team="Test Team",
        axes=_minimal_axes(),
        models=["model-a", "model-b", "model-c"],
    )
    assert len(cfg.models) == 3


def test_submission_config_optional_fields() -> None:
    cfg = SubmissionConfig(
        name="Test System",
        team="Test Team",
        axes=_minimal_axes(),
        models=["model-a"],
        paper_url="https://arxiv.org/abs/0000.00001",
        resources="2x A100",
        license="Apache-2.0",
        acknowledgments="Thanks",
    )
    assert cfg.paper_url == "https://arxiv.org/abs/0000.00001"
    assert cfg.resources == "2x A100"
    assert cfg.license == "Apache-2.0"
    assert cfg.acknowledgments == "Thanks"


# ---------------------------------------------------------------------------
# load_submission_config round-trip
# ---------------------------------------------------------------------------


def test_load_round_trip(tmp_path: Any) -> None:
    """model_dump then reload via YAML produces equivalent config."""
    import yaml

    yaml_path: Path = tmp_path / "submission.yaml"
    original = SubmissionConfig(
        name="Round-Trip System",
        team="RT Team",
        axes=_minimal_axes(),
        models=["sonnet-4-6"],
        paper_url="https://example.com/paper",
    )
    # Dump to YAML manually
    data = {
        "name": original.name,
        "team": original.team,
        "axes": {
            "retrieval": original.axes.retrieval,
            "ingestion": original.axes.ingestion,
            "assistant": original.axes.assistant,
        },
        "models": list(original.models),
        "paper_url": original.paper_url,
    }
    yaml_path.write_text(yaml.dump(data), encoding="utf-8")
    loaded = load_submission_config(yaml_path)
    assert loaded.name == original.name
    assert loaded.team == original.team
    assert loaded.models == original.models
    assert loaded.paper_url == original.paper_url


def test_load_raises_on_missing_name(tmp_path: Any) -> None:
    yaml_path: Path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        "team: T\naxes:\n  retrieval: true\n  ingestion: false\n"
        "  assistant: true\nmodels:\n  - m\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="name"):
        load_submission_config(yaml_path)


def test_load_raises_on_axes_unknown_field(tmp_path: Any) -> None:
    yaml_path: Path = tmp_path / "submission.yaml"
    yaml_path.write_text(
        (
            "name: N\nteam: T\naxes:\n  retrieval: true\n  ingestion: false\n"
            "  assistant: true\n  extra_axis: true\nmodels:\n  - m\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_submission_config(yaml_path)


def test_load_file_path_in_error_message(tmp_path: Any) -> None:
    """ValueError includes the file path for debugging."""
    yaml_path: Path = tmp_path / "my_submission.yaml"
    yaml_path.write_text("not: a: valid: structure\n  broken", encoding="utf-8")
    with pytest.raises(ValueError) as exc_info:
        load_submission_config(yaml_path)
    assert "my_submission.yaml" in str(exc_info.value)
