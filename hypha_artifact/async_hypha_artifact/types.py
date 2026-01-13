"""Async-specific re-exports for type consistency.

This module re-exports types that are defined centrally to avoid duplication
and circular imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from types import TracebackType

from hypha_artifact.classes import (
    MultipartConfig,
    MultipartStatusMessage,
    UploadPartServerInfo,
)

__all__ = [
    "ArtifactIdParams",
    "AsyncBinaryFile",
    "CommitParams",
    "CompleteMultipartParams",
    "CompletedPart",
    "CreateParams",
    "DeleteParams",
    "EditParams",
    "GetFileUrlParams",
    "ListChildrenParams",
    "ListFilesParams",
    "MultipartConfig",
    "MultipartStatusMessage",
    "PreparedPartInfo",
    "RemoveFileParams",
    "StartMultipartParams",
    "SyncBinaryFile",
    "UploadPartServerInfo",
]


@runtime_checkable
class AsyncBinaryFile(Protocol):
    """Protocol for async binary file-like objects."""

    async def __aenter__(self) -> Self:
        """Enter the context."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit the context."""
        ...

    async def read(self) -> bytes:
        """Read bytes from the file."""
        ...

    async def write(self, data: bytes) -> int:
        """Write bytes to the file."""
        ...

    async def close(self) -> None:
        """Close the file."""
        ...


class SyncBinaryFile(Protocol):
    """Protocol for sync binary file-like objects."""

    def read(self, size: int = ...) -> bytes:
        """Read bytes from the file."""
        ...

    def write(self, data: bytes) -> int:
        """Write bytes to the file."""
        ...

    def close(self) -> None:
        """Close the file."""
        ...


class ListChildrenParams(TypedDict):
    """Parameters for listing children."""

    parent_id: str
    keywords: list[str] | None
    filters: Mapping[str, object] | None
    mode: str | None
    offset: int | None
    limit: int | None
    order_by: str | None
    silent: bool | None
    stage: bool | None


class CreateParams(TypedDict):
    """Parameters for creating an artifact."""

    alias: str
    workspace: str | None
    parent_id: str | None
    type: str | None
    manifest: Mapping[str, object] | None
    config: Mapping[str, object] | None
    version: str | None
    stage: bool | None
    comment: str | None
    secrets: Mapping[str, str] | None
    overwrite: bool | None


class ArtifactIdParams(TypedDict):
    """Parameters identifying an artifact."""

    artifact_id: str


class ListFilesParams(ArtifactIdParams):
    """Parameters for listing files."""

    dir_path: str
    limit: int | None
    version: str | None


class GetFileUrlParams(ArtifactIdParams):
    """Parameters for getting file URLs."""

    file_path: str | list[str]
    version: str | None
    use_proxy: bool | None
    use_local_url: bool | str | None


class RemoveFileParams(ArtifactIdParams):
    """Parameters for removing a file."""

    file_path: str


class StartMultipartParams(ArtifactIdParams):
    """Parameters for starting multipart upload."""

    file_path: str
    part_count: int
    download_weight: float | None
    use_proxy: bool | None
    use_local_url: bool | str | None


class CompleteMultipartParams(ArtifactIdParams):
    """Parameters for completing multipart upload."""

    upload_id: str
    parts: Sequence[CompletedPart]


class EditParams(ArtifactIdParams):
    """Parameters for editing an artifact."""

    manifest: Mapping[str, object] | None
    type: str | None
    config: Mapping[str, object] | None
    secrets: Mapping[str, str] | None
    version: str | None
    comment: str | None
    stage: bool | None


class CommitParams(ArtifactIdParams):
    """Parameters for committing changes."""

    version: str | None
    comment: str | None


class DeleteParams(ArtifactIdParams):
    """Parameters for deleting an artifact."""

    delete_files: bool | None
    recursive: bool | None
    version: str | None


class PreparedPartInfo(TypedDict):
    """Client-prepared part info with data to upload."""

    url: str
    part_number: int
    chunk: bytes
    part_size: int


class CompletedPart(TypedDict):
    """Completed part info used to finalize multipart upload."""

    part_number: int
    etag: str
