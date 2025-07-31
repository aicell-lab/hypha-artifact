"""Utility functions for Hypha Artifact."""

from typing import Any, Literal

FileMode = Literal["r", "rb", "w", "wb", "a", "ab"]
OnError = Literal["raise", "ignore"]
JsonType = str | int | float | bool | None | dict[str, Any] | list[Any]


def remove_none(d: dict[Any, Any]) -> dict[Any, Any]:
    """Remove None values from a dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def parent_and_filename(path: str) -> tuple[str | None, str]:
    """Get the parent directory of a path"""
    parts = path.rstrip("/").split("/")
    if len(parts) == 1:
        return None, parts[-1]  # Root directory
    return "/".join(parts[:-1]), parts[-1]


def normalize_path(path: str) -> str:
    """Normalize the path by removing all leading slashes."""
    return path.lstrip("/")
