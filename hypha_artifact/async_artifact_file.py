"""Async artifact file handling for Hypha."""

import io
import locale
import os
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Self

import httpx


class AsyncArtifactHttpFile:
    """An async file-like object that supports async context manager protocols.

    This implements an async file interface for Hypha artifacts,
    handling HTTP operations via the httpx library.
    """

    name: str | None
    etag: str | None

    def __init__(
        self: Self,
        url_func: Callable[[], Awaitable[str]],
        mode: str = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        content_type: str = "",
        *,
        ssl: bool | None = None,
    ) -> None:
        """Initialize an AsyncArtifactHttpFile instance.

        Args:
            self (Self): The instance of the AsyncArtifactHttpFile class.
            url_func (Callable[[], Awaitable[str]]): A function that returns the URL
                for the file.
            mode (str, optional): The mode in which to open the file. Defaults to "r".
            encoding (str | None, optional): The encoding to use for the file.
                Defaults to None.
            newline (str | None, optional): The newline character to use.
                Defaults to None.
            name (str | None, optional): The name of the file. Defaults to None.
            content_type (str, optional): The content type of the file. Defaults to "".
            ssl (bool | None, optional): Whether to use SSL. Defaults to None.

        """
        self._url_func = url_func
        self._url: str | None = None
        self._pos = 0
        self._mode = mode
        self._encoding = encoding or locale.getpreferredencoding()
        self._newline = newline or os.linesep
        self._closed = False
        self._buffer = io.BytesIO()
        self._client: httpx.AsyncClient | None = None
        self._timeout = 120
        self._content_type = content_type
        self._ssl = ssl
        self.name = name
        self.etag = None

        if "r" in mode:
            self._size = 0  # Will be set when content is downloaded
        else:
            # For write modes, initialize an empty buffer
            self._size = 0

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(verify=bool(self._ssl))
        if "r" in self._mode:
            await self.download_content()
        return self

    async def __aexit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def get_url(self: Self) -> str:
        """Get the URL for this file."""
        if self._url is None:
            self._url = await self._url_func()
        return self._url

    def _get_client(self: Self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(verify=bool(self._ssl))
        return self._client

    async def download_content(self: Self, range_header: str | None = None) -> None:
        """Download content from URL into buffer, optionally using a range header."""
        url = await self.get_url()
        try:

            headers: dict[str, str] = {
                "Accept-Encoding": "identity",  # Prevent gzip compression
            }
            if range_header:
                headers["Range"] = range_header

            client = self._get_client()
            response = await client.get(url, headers=headers, timeout=60)
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
            error_msg = (
                f"Error downloading content from {url}"
                f" (status {status_code}): {message}"
            )
            raise OSError(
                error_msg,
            ) from e
        except Exception as e:
            error_msg = f"Unexpected error downloading content: {e!s}"
            raise OSError(error_msg) from e

    async def upload_content(self: Self) -> httpx.Response:
        """Upload buffer content to URL."""
        response: httpx.Response
        try:
            content = self._buffer.getvalue()
            url = await self.get_url()

            headers = {
                "Content-Type": self._content_type,
                "Content-Length": str(len(content)),
            }

            client = self._get_client()
            response = await client.put(
                url,
                content=content,
                headers=headers,
                timeout=self._timeout,
            )

            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            status_code = (
                e.response.status_code if hasattr(e, "response") else "unknown"
            )
            error_msg = e.response.text if hasattr(e, "response") else str(e)
            full_error_msg = (
                f"HTTP error uploading content (status {status_code}): {error_msg}"
            )
            raise OSError(full_error_msg) from e
        except Exception as e:
            error_msg = f"Error uploading content: {e!s}"
            raise OSError(error_msg) from e
        else:
            return response

    def tell(self: Self) -> int:
        """Return current position in the file."""
        return self._pos

    def seek(self: Self, offset: int, whence: int = 0) -> int:
        """Change stream position."""
        if whence == os.SEEK_SET:
            self._pos = offset
        elif whence == os.SEEK_CUR:
            self._pos += offset
        elif whence == os.SEEK_END:
            self._pos = self._size + offset

        # Make sure buffer's position is synced
        self._buffer.seek(self._pos)
        return self._pos

    async def read(self: Self, size: int = -1) -> bytes | str:
        """Read up to size bytes from the file, using HTTP range if necessary."""
        if "r" not in self._mode:
            error_msg = "File not open for reading"
            raise OSError(error_msg)

        if size < 0:
            await self.download_content()
        else:
            range_header = f"bytes={self._pos}-{self._pos + size - 1}"
            await self.download_content(range_header=range_header)

        data = self._buffer.read()
        self._pos += len(data)

        if "b" not in self._mode:
            return data.decode(self._encoding)
        return data

    async def write(self: Self, data: str | bytes) -> int:
        """Write data to the file."""
        if "w" not in self._mode and "a" not in self._mode:
            error_msg = "File not open for writing"
            raise OSError(error_msg)

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

    def ensure_etag(self: Self) -> None:
        """Ensure that the ETag is set after upload."""
        if not self.etag:
            error_msg = "ETag must be set after upload"
            raise OSError(error_msg)

    async def close(self: Self) -> None:
        """Close the file and upload content if in write mode."""
        if self._closed:
            return

        try:
            if "w" in self._mode or "a" in self._mode:
                response = await self.upload_content()
                self.etag = response.headers.get("ETag", "").strip('"')
                self.ensure_etag()
        finally:
            self._closed = True
            self._buffer.close()
            if self._client:
                await self._client.aclose()

    @property
    def closed(self: Self) -> bool:
        """Return whether the file is closed."""
        return self._closed

    def readable(self: Self) -> bool:
        """Return whether the file is readable."""
        return "r" in self._mode

    def writable(self: Self) -> bool:
        """Return whether the file is writable."""
        return "w" in self._mode or "a" in self._mode

    def seekable(self: Self) -> bool:
        """Return whether the file supports seeking."""
        return True
