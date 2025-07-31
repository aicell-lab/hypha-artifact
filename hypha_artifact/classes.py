"""Represents a file or directory in the artifact storage."""

from typing import TypedDict, Literal


class ArtifactItem(TypedDict):
    """
    Represents an item in the artifact, containing metadata and content.
    """

    name: str
    type: Literal["file", "directory"]
    size: int
    last_modified: float | None
