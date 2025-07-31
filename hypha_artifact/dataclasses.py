from dataclasses import dataclass
from typing import Literal


@dataclass
class ArtifactItem:
    """
    Represents information about a file in a Hypha artifact.

    Attributes:
        type (Literal["file", "directory"]): The type of the item, either "file" or "directory".
        name (str): The name of the file.
        size (int): The size of the file in bytes.
        last_modified (str | None): The last modified timestamp of the file.
    """

    type: Literal["file"] | Literal["directory"]
    name: str
    size: int
    last_modified: float | None = None
