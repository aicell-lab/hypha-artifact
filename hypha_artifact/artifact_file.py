# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Artifact file handling for Hypha."""

import io
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Generic, Self, TypeVar

import httpx

from .async_artifact_file import AsyncArtifactHttpFile
from .sync_utils import run_sync

if TYPE_CHECKING:
    from _typeshed import OpenBinaryMode, OpenTextMode
else:
    OpenBinaryMode = str
    OpenTextMode = str

T = TypeVar("T", str, bytes)


class ArtifactHttpFile(io.IOBase, Generic[T]):
    """A file-like object that supports both sync and async context manager protocols.

    This implements a file interface for Hypha artifacts, handling HTTP operations
    via the httpx library instead of relying on Pyodide.
    """

    name: str | None
    mode: OpenBinaryMode | OpenTextMode

    def __init__(
        self: Self,
        url: str | None = None,
        mode: OpenBinaryMode | OpenTextMode = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        additional_headers: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize an ArtifactHttpFile instance.

        Args:
            self (Self): The instance itself.
            url (str): The URL of the artifact file.
            mode (str, optional): The mode in which to open the file. Defaults to "r".
            encoding (str | None, optional): The encoding to use for the file.
                Defaults to None.
            newline (str | None, optional): The newline character to use for the file.
                Defaults to None.
            name (str | None, optional): The name of the file. Defaults to None.
            additional_headers (Mapping[str, str] | None, optional): Extra headers to
                include with HTTP requests. Defaults to None.

        """
        self._async_file = AsyncArtifactHttpFile(
            url=url,
            mode=mode,
            encoding=encoding,
            newline=newline,
            name=name,
            additional_headers=additional_headers,
        )

    def __enter__(self: Self) -> Self:
        """Enter context manager."""
        run_sync(self._async_file.__aenter__())

        return self

    def __exit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        run_sync(self._async_file.__aexit__(exc_type, exc_val, exc_tb))

    def download_content(self: Self, range_header: str | None = None) -> None:
        """Download content from URL into buffer, optionally using a range header."""
        run_sync(self._async_file.download_content(range_header))

    def upload_content(self: Self) -> httpx.Response:
        """Upload content from buffer to the remote URL."""
        return run_sync(self._async_file.upload_content())

    def tell(self: Self) -> int:
        """Return current position in the file."""
        return self._async_file.tell()

    def seek(self: Self, offset: int, whence: int = 0) -> int:
        """Change stream position."""
        return self._async_file.seek(offset, whence)

    def read(self: Self, size: int = -1) -> bytes | str:
        """Read up to size bytes from the file, using HTTP range if necessary."""
        return run_sync(self._async_file.read(size))

    def write(self: Self, data: str | bytes) -> int:
        """Write data to the file."""
        return run_sync(self._async_file.write(data))

    def readable(self: Self) -> bool:
        """Return whether the file is readable."""
        return self._async_file.readable()

    def writable(self: Self) -> bool:
        """Return whether the file is writable."""
        return self._async_file.writable()

    def seekable(self: Self) -> bool:
        """Return whether the file is seekable."""
        return self._async_file.seekable()

    def close(self: Self) -> None:
        """Close the file and upload content if in write mode."""
        run_sync(self._async_file.close())

    @property
    def closed(self: Self) -> bool:
        """Return whether the file is closed."""
        return self._async_file.closed
