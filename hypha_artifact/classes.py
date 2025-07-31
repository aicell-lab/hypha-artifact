"""Represents a file or directory in the artifact storage."""

from dataclasses import dataclass
from typing import Any, TypedDict, Literal


class ArtifactItem(TypedDict):
    """
    Represents an item in the artifact, containing metadata and content.
    """

    name: str
    type: Literal["file", "directory"]
    size: int
    last_modified: float | None


@dataclass
class TransferPaths:
    """Helper class to store source and destination paths."""

    src: str
    dst: str


class StatusMessage:
    """Class to represent a status message for file operations."""

    def __init__(self, operation: str, total_files: int):
        self.operation = operation
        self.total_files = total_files

    def in_progress(
        self: "StatusMessage", file_path: str, current_file_index: int
    ) -> dict[str, Any]:
        """Create a message indicating the progress of an operation."""
        return {
            "type": "info",
            "message": (
                f"{self.operation.capitalize()}ing file"
                f" {current_file_index + 1}/{self.total_files}: {file_path}"
            ),
            "file": file_path,
            "total_files": self.total_files,
            "current_file": current_file_index + 1,
        }

    def success(self: "StatusMessage", file_path: str) -> dict[str, Any]:
        """Create a message indicating a successful operation."""
        return {
            "type": "success",
            "message": f"Successfully {self.operation}ed: {file_path}",
            "file": file_path,
        }

    def error(
        self: "StatusMessage", file_path: str, error_message: str
    ) -> dict[str, Any]:
        """Create a message indicating an error during the operation."""
        return {
            "type": "error",
            "message": f"Failed to {self.operation} {file_path}: {error_message}",
            "file": file_path,
        }
