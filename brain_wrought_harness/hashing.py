"""Deterministic submission hash for reproducible evaluation records."""
from __future__ import annotations

import hashlib
import subprocess
from importlib.metadata import version


def get_harness_version() -> str:
    """Return the installed package version via importlib.metadata."""
    return version("brain-wrought")


def get_image_digest(docker_image: str) -> str:
    """Get the Docker image content digest via docker inspect."""
    result = subprocess.run(
        ["docker", "inspect", "--format={{.Id}}", docker_image],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker inspect failed: {result.stderr[:200]}")
    return result.stdout.strip()


def compute_submission_hash(docker_image_digest: str, harness_version: str) -> str:
    """SHA-256 of '{digest}:{version}'."""
    payload = f"{docker_image_digest}:{harness_version}"
    return hashlib.sha256(payload.encode()).hexdigest()
