"""Path helpers."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the RemedyPDF project root (parent of src/)."""
    return Path(__file__).resolve().parent.parent.parent


def resources_dir() -> Path:
    return project_root() / "resources"
