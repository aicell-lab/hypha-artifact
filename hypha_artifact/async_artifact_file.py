"""Async artifact file handling for Hypha."""

import io
import locale
import os
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Generic, Self, TypeVar, overload

import httpx

if TYPE_CHECKING:
    from _typeshed import OpenBinaryMode, OpenTextMode
else:
    OpenBinaryMode = str
    OpenTextMode = str

DataType = TypeVar("DataType", str, bytes)
OpenMode = OpenBinaryMode | OpenTextMode


class AsyncArtifactHttpFile(Generic[DataType]):
    """An async file-like object that supports async context manager protocols.

    This implements an async file interface for Hypha artifacts,
    handling HTTP operations via the httpx library.
    """

    name: str | None
    etag: str | None

    # Constructor overloads tie mode to the instance data type
    @overload
    def __init__(
        self: "AsyncArtifactHttpFile[str]",
        url: str | None = None,
        mode: OpenTextMode = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        content_type: str = "",
        *,
        ssl: bool | None = None,
        additional_headers: Mapping[str, str] | None = None,
        url_factory: Callable[[], Awaitable[str]] | None = None,
    ) -> None: ...

    @overload
    def __init__(
        self: "AsyncArtifactHttpFile[bytes]",
        url: str | None = None,
        mode: OpenBinaryMode = "rb",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        content_type: str = "",
        *,
        ssl: bool | None = None,
        additional_headers: Mapping[str, str] | None = None,
        url_factory: Callable[[], Awaitable[str]] | None = None,
    ) -> None: ...

    def __init__(
        self: Self,
        url: str | None = None,
        mode: OpenMode = "r",
        encoding: str | None = None,
        newline: str | None = None,
        name: str | None = None,
        content_type: str = "",
        *,
        ssl: bool | None = None,
        additional_headers: Mapping[str, str] | None = None,
        url_factory: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        """Initialize an AsyncArtifactHttpFile instance.

        Args:
            self (Self): The instance of the AsyncArtifactHttpFile class.
            url (str): The URL of the artifact file.
            mode (str, optional): The mode in which to open the file. Defaults to "r".
            encoding (str | None, optional): The encoding to use for the file.
                Defaults to None.
            newline (str | None, optional): The newline character to use.
                Defaults to None.
            name (str | None, optional): The name of the file. Defaults to None.
            content_type (str, optional): The content type of the file. Defaults to "".
            ssl (bool | None, optional): Whether to use SSL. Defaults to None.
            additional_headers (Mapping[str, str] | None, optional): Extra headers
                to include with HTTP requests. Defaults to None.
            url_factory (Callable[[], Awaitable[str]] | None, optional):
                Async function to resolve the URL lazily when entering the
                context manager. If provided, it will be used when `url` is
                not set. Defaults to None.

        """
        if not url and url_factory is None:
            error_msg = "Either url or url_factory must be provided"
            raise ValueError(error_msg)

        self._url = url
        self._url_factory = url_factory
        self._pos = 0
        self._encoding = encoding or locale.getpreferredencoding()
        self._newline = newline or os.linesep
        self._closed = False
        self._buffer = io.BytesIO()
        self._client: httpx.AsyncClient | None = None
        self._timeout = 120
        self._content_type = content_type
        self._ssl = ssl
        self._additional_headers = dict(additional_headers or {})
        self.name = name
        self.etag = None
        self._size = 0
        self._mode = mode

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(verify=bool(self._ssl))
        if not self._url:
            if self._url_factory is None:
                error_msg = "URL not provided and url_factory missing"
                raise OSError(error_msg)
            self._url = await self._url_factory()
        if self.readable():
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

    def _get_client(self: Self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None:
            self._client = httpx.AsyncClient(verify=bool(self._ssl))
        return self._client

    async def download_content(self: Self, range_header: str | None = None) -> None:
        """Download content from URL into buffer, optionally using a range header."""
        try:

            headers: dict[str, str] = {
                "Accept-Encoding": "identity",  # Prevent gzip compression
            }
            if self._additional_headers:
                headers.update(self._additional_headers)
            if range_header:
                headers["Range"] = range_header

            client = self._get_client()
            url = self._require_url()
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
                f"Error downloading content from {self._url}"
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

            headers = {
                "Content-Type": self._content_type,
                "Content-Length": str(len(content)),
            }
            if self._additional_headers:
                headers.update(self._additional_headers)

            client = self._get_client()
            url = self._require_url()
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

    @overload
    async def read(self: "AsyncArtifactHttpFile[bytes]", size: int = -1) -> bytes: ...

    @overload
    async def read(self: "AsyncArtifactHttpFile[str]", size: int = -1) -> str: ...

    async def read(self: Self, size: int = -1) -> bytes | str:
        """Read up to size bytes from the file, using HTTP range if necessary."""
        if not self.readable():
            error_msg = "File not open for reading"
            raise OSError(error_msg)

        if size < 0:
            await self.download_content()
        else:
            range_header = f"bytes={self._pos}-{self._pos + size - 1}"
            await self.download_content(range_header=range_header)

        data = self._buffer.read()
        self._pos += len(data)

        if self._is_binary():
            return data
        return data.decode(self._encoding)

    async def write(self: Self, data: str | bytes) -> int:
        """Write data to the file."""
        if not self.writable():
            error_msg = "File not open for writing"
            raise OSError(error_msg)

        # Convert string to bytes if necessary
        if isinstance(data, str) and self._is_binary():
            data = data.encode(self._encoding)
        elif isinstance(data, bytes) and not self._is_binary():
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
            if self.writable():
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

    def _require_url(self: Self) -> str:
        """Return a resolved URL or raise if unavailable.

        This helps type checkers understand that from this point on, the URL is str.
        """
        if not self._url:
            error_msg = "URL is not resolved yet"
            raise OSError(error_msg)
        return self._url

    def _is_binary(
        self: Self,
    ) -> bool:
        """Whether opened in binary mode."""
        return "b" in self._mode
