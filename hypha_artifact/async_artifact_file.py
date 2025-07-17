"""Async artifact file handling for Hypha."""

import io
import locale
import os
from collections.abc import Callable, Awaitable
from typing import Self
from types import TracebackType
import httpx
from hypha_artifact.utils import clean_url, FileMode


class AsyncArtifactHttpFile:
    """An async file-like object that supports async context manager protocols.

    This implements an async file interface for Hypha artifacts, handling HTTP operations
    via the httpx library.
    """

    name: str | None
    mode: str
    auto_commit: bool
    commit_func: Callable[[], Awaitable[None]] | None

    def __init__(
        self: Self,
        url_func: Callable[[], Awaitable[str]],
        mode: FileMode = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        auto_commit: bool = True,
        commit_func: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._url_func = url_func
        self._url: str | None = None
        self._pos = 0
        self._mode = mode
        self._encoding = encoding or locale.getpreferredencoding()
        self._newline = newline or os.linesep
        self.name = name
        self._closed = False
        self._buffer = io.BytesIO()
        self._auto_commit = auto_commit
        self._commit_func = commit_func
        self._client: httpx.AsyncClient | None = None

        if "r" in mode:
            self._size = 0  # Will be set when content is downloaded
        else:
            # For write modes, initialize an empty buffer
            self._size = 0

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        self._client = httpx.AsyncClient()
        if "r" in self._mode:
            await self._download_content()
        return self

    async def __aexit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def _get_url(self: Self) -> str:
        """Get the URL for this file."""
        if self._url is None:
            self._url = await self._url_func()
        return self._url

    def _get_client(self: Self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient()
        return self._client

    async def _download_content(self: Self, range_header: str | None = None) -> None:
        """Download content from URL into buffer, optionally using a range header."""
        try:
            url = await self._get_url()
            # Clean the URL by removing any surrounding quotes and converting to string if needed
            cleaned_url = clean_url(url)

            headers: dict[str, str] = {}
            if range_header:
                headers["Range"] = range_header

            async with self._get_client() as client:
                response = await client.get(cleaned_url, headers=headers, timeout=60)
                response.raise_for_status()
                self._buffer = io.BytesIO(response.content)
                self._size = len(response.content)
        except httpx.RequestError as e:
            # More detailed error information for debugging
            status_code = (
                getattr(e.request, "status_code", "unknown")
                if hasattr(e, "request")
                else "unknown"
            )
            message = str(e)
            raise IOError(
                f"Error downloading content (status {status_code}): {message}"
            ) from e
        except Exception as e:
            raise IOError(f"Unexpected error downloading content: {str(e)}") from e

    async def _upload_content(self: Self) -> httpx.Response:
        """Upload buffer content to URL"""
        try:
            content = self._buffer.getvalue()
            url = await self._get_url()
            cleaned_url = clean_url(url)

            headers = {
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
            }

            async with self._get_client() as client:
                response = await client.put(
                    cleaned_url, content=content, headers=headers, timeout=60
                )
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as e:
            status_code = (
                e.response.status_code if hasattr(e, "response") else "unknown"
            )
            error_msg = e.response.text if hasattr(e, "response") else str(e)
            raise IOError(
                f"HTTP error uploading content (status {status_code}): {error_msg}"
            ) from e
        except Exception as e:
            raise IOError(f"Error uploading content: {str(e)}") from e

    def tell(self: Self) -> int:
        """Return current position in the file"""
        return self._pos

    def seek(self: Self, offset: int, whence: int = 0) -> int:
        """Change stream position"""
        if whence == 0:  # os.SEEK_SET
            self._pos = offset
        elif whence == 1:  # os.SEEK_CUR
            self._pos += offset
        elif whence == 2:  # os.SEEK_END
            self._pos = self._size + offset

        # Make sure buffer's position is synced
        self._buffer.seek(self._pos)
        return self._pos

    async def read(self: Self, size: int = -1) -> bytes | str:
        """Read up to size bytes from the file, using HTTP range if necessary."""
        if "r" not in self._mode:
            raise IOError("File not open for reading")

        if size < 0:
            await self._download_content()
        else:
            range_header = f"bytes={self._pos}-{self._pos + size - 1}"
            await self._download_content(range_header=range_header)

        data = self._buffer.read()
        self._pos += len(data)

        if "b" not in self._mode:
            return data.decode(self._encoding)
        return data

    async def write(self: Self, data: str | bytes) -> int:
        """Write data to the file"""
        if "w" not in self._mode and "a" not in self._mode:
            raise IOError("File not open for writing")

        # Convert string to bytes if necessary
        if isinstance(data, str) and "b" in self._mode:
            data = data.encode(self._encoding)
        elif isinstance(data, bytes) and "b" not in self._mode:
            data = data.decode(self._encoding)
            data = data.encode(self._encoding)

        # Ensure we're at the right position
        self._buffer.seek(self._pos)

        # Write the data
        if isinstance(data, str):
            data = data.encode(self._encoding)
        bytes_written = self._buffer.write(data)
        self._pos += bytes_written
        self._size = max(self._size, self._pos)

        return bytes_written

    async def close(self: Self) -> None:
        """Close the file and upload content if in write mode"""
        if self._closed:
            return

        try:
            if ("w" in self._mode or "a" in self._mode) and self._buffer.tell() > 0:
                await self._upload_content()
                if self._auto_commit and self._commit_func:
                    await self._commit_func()
        finally:
            self._closed = True
            self._buffer.close()
            if self._client:
                await self._client.aclose()

    @property
    def closed(self: Self) -> bool:
        """Return whether the file is closed"""
        return self._closed

    def readable(self: Self) -> bool:
        """Return whether the file is readable"""
        return "r" in self._mode

    def writable(self: Self) -> bool:
        """Return whether the file is writable"""
        return "w" in self._mode or "a" in self._mode

    def seekable(self: Self) -> bool:
        """Return whether the file supports seeking"""
        return True
