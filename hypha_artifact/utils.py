"""Utility functions for Hypha Artifact."""

import json
from typing import Any, Literal

OnError = Literal["raise", "ignore"]
JsonType = str | int | float | bool | None | dict[str, Any] | list[Any]


def remove_none(d: dict[Any, Any]) -> dict[Any, Any]:
    """Remove None values from a dictionary."""
    return {k: v for k, v in d.items() if v is not None}


def prepare_params(
    params: dict[str, JsonType],
    artifact_id: str,
) -> dict[str, JsonType]:
    """Extend parameters with artifact_id."""
    cleaned_params = remove_none(params)
    cleaned_params["artifact_id"] = artifact_id
    return cleaned_params


def ensure_dict(obj: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Ensures the given object is a dictionary."""
    if isinstance(obj, dict):
        return obj

    if isinstance(obj, str):
        return json.loads(obj)

    return None
