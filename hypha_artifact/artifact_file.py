# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Artifact file handling for Hypha."""

import contextlib
import io
from types import TracebackType
from typing import TYPE_CHECKING, Self

import httpx

from .async_artifact_file import AsyncArtifactHttpFile
from .sync_utils import run_sync

if not TYPE_CHECKING:
    try:
        # Try to import the pyodide-specific run_sync
        from pyodide.ffi import run_sync
    except ImportError:
        # Fallback to the default implementation if pyodide is not available
        contextlib.suppress(ImportError)


class ArtifactHttpFile(io.IOBase):
    """A file-like object that supports both sync and async context manager protocols.

    This implements a file interface for Hypha artifacts, handling HTTP operations
    via the httpx library instead of relying on Pyodide.
    """

    name: str | None
    mode: str

    def __init__(
        self: Self,
        url: str,
        mode: str = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
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

        """

        async def get_url() -> str:
            """Get the URL for the artifact file."""
            return url

        self._async_file = AsyncArtifactHttpFile(
            url_func=get_url,
            mode=mode,
            encoding=encoding,
            newline=newline,
            name=name,
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
