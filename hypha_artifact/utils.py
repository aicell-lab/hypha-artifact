"""Utility functions for Hypha Artifact."""

from pathlib import Path
from typing import Any, Literal

FileMode = Literal["r", "rb", "w", "wb", "a", "ab"]
OnError = Literal["raise", "ignore"]
JsonType = str | int | float | bool | None | dict[str, Any] | list[Any]


def remove_none(d: dict[Any, Any]) -> dict[Any, Any]:
    """Remove None values from a dictionary."""
    return {k: v for k, v in d.items() if v is not None}
