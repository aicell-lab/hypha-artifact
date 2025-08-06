"""Methods for file I/O operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    overload,
)

import httpx

from ..utils import OnError
from ..async_artifact_file import AsyncArtifactHttpFile

from ._remote import remote_get_file_url, remote_put_file_url
from ._utils import (
    copy_single_file,
    transfer,
    upload_multipart,
)

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


@overload
async def cat(
    self: "AsyncHyphaArtifact",
    path: list[str],
    recursive: bool = False,
    on_error: OnError = "raise",
) -> dict[str, str | None]: ...


@overload
async def cat(
    self: "AsyncHyphaArtifact",
    path: str,
    recursive: bool = False,
    on_error: OnError = "raise",
) -> str | None: ...


async def cat(
    self: "AsyncHyphaArtifact",
    path: str | list[str],
    recursive: bool = False,
    on_error: OnError = "raise",
) -> dict[str, str | None] | str | None:
    """Get file(s) content as string(s)

    Parameters
    ----------
    path: str or list of str
        File path(s) to get content from
    recursive: bool
        If True and path is a directory, get all files content
    on_error: "raise" or "ignore"
        What to do if a file is not found

    Returns
    -------
    str or dict or None
        File contents as string if path is a string, dict of {path: content} if path is a list,
        or None if the file is not found and on_error is "ignore"
    """
    if isinstance(path, list):
        results: dict[str, str | None] = {}
        for p in path:
            results[p] = await self.cat(p, recursive=recursive, on_error=on_error)
        return results

    if recursive and await self.isdir(path):
        results = {}
        files = await self.find(path, withdirs=False)
        for file_path in files:
            results[file_path] = await self.cat(file_path, on_error=on_error)
        return results

    try:
        async with self.open(path, "r") as f:
            content = await f.read()
            if isinstance(content, bytes):
                return content.decode("utf-8")
            elif isinstance(content, (bytearray, memoryview)):
                return bytes(content).decode("utf-8")
            return str(content)
    except (FileNotFoundError, IOError, httpx.RequestError) as e:
        if on_error == "ignore":
            return None
        raise e


def fsspec_open(
    self: "AsyncHyphaArtifact",
    urlpath: str,
    mode: str = "rb",
    content_type: str = "application/octet-stream",
    **kwargs: Any,
) -> AsyncArtifactHttpFile:
    """Open a file for reading or writing

    Parameters
    ----------
    urlpath: str
        Path to the file within the artifact
    mode: str
        File mode, similar to 'r', 'rb', 'w', 'wb', 'a', 'ab'

    Returns
    -------
    AsyncArtifactHttpFile
        A file-like object
    """
    if "r" in mode:

        async def get_url():
            return await remote_get_file_url(self, urlpath)

    elif "w" in mode or "a" in mode:

        async def get_url():
            url = await remote_put_file_url(self, urlpath)
            return url

    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return AsyncArtifactHttpFile(
        url_func=get_url,
        mode=mode,
        name=str(urlpath),
        content_type=content_type,
        ssl=self.ssl,
    )


async def copy(
    self: "AsyncHyphaArtifact",
    path1: str,
    path2: str,
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError | None = "raise",
    **kwargs: dict[str, Any],
) -> None:
    """Copy file(s) from path1 to path2 within the artifact

    Parameters
    ----------
    path1: str
        Source path
    path2: str
        Destination path
    recursive: bool
        If True and path1 is a directory, copy all its contents recursively
    maxdepth: int or None
        Maximum recursion depth when recursive=True
    on_error: "raise" or "ignore"
        What to do if a file is not found
    """
    if recursive and await self.isdir(path1):
        files = await self.find(path1, maxdepth=maxdepth, withdirs=False)
        for src_path in files:
            rel_path = Path(src_path).relative_to(path1)
            dst_path = Path(path2) / rel_path
            try:
                await copy_single_file(self, src_path, str(dst_path))
            except (FileNotFoundError, IOError, httpx.RequestError) as e:
                if on_error == "raise":
                    raise e
    else:
        await copy_single_file(self, path1, path2)


async def get(
    self: "AsyncHyphaArtifact",
    rpath: str | list[str],
    lpath: str | list[str],
    recursive: bool = False,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    **kwargs: Any,
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem."""
    await transfer(
        self,
        rpath=rpath,
        lpath=lpath,
        recursive=recursive,
        callback=callback,
        maxdepth=maxdepth,
        on_error=on_error,
        transfer_type="GET",
    )


async def upload(
    self: "AsyncHyphaArtifact",
    local_path: str | Path,
    remote_path: str = "",
    recursive: bool = True,
    enable_multipart: bool = False,
    multipart_threshold: int = 100 * 1024 * 1024,  # 100MB
    chunk_size: int = 10 * 1024 * 1024,  # 10MB per part
    max_parallel_uploads: int = 4,
) -> None:
    """Upload a file or folder to the artifact with optional multipart upload.

    Parameters
    ----------
    local_path: str or Path
        Path to the local file or folder to upload
    remote_path: str
        Path within the artifact where the content will be stored (default: same name)
    recursive: bool
        Whether to upload subdirectories recursively when uploading folders (default: True)
    enable_multipart: bool
        Force multipart upload even for small files (default: False)
    multipart_threshold: int
        File size threshold for automatic multipart upload (default: 100MB)
    chunk_size: int
        Size of each part in multipart upload (default: 10MB)
    max_parallel_uploads: int
        Maximum number of parallel part uploads (default: 4)
    auto_commit: bool
        Whether to automatically commit after upload (default: True)
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local path does not exist: {local_path}")

    # If no remote_path specified, use the local name
    if not remote_path:
        remote_path = local_path.name

    if local_path.is_file():
        # Upload single file
        file_size = local_path.stat().st_size
        use_multipart = enable_multipart or file_size >= multipart_threshold

        if use_multipart and file_size > chunk_size:
            await upload_multipart(
                self,
                local_path,
                remote_path,
                chunk_size,
                max_parallel_uploads,
            )
        else:
            # TODO: download_weight
            await put(
                self,
                str(local_path),
                str(remote_path),
            )

    elif local_path.is_dir():

        try:
            files_to_upload: list[tuple[Path, str]] = []
            if recursive:
                for file_path in local_path.rglob("*"):
                    if file_path.is_file():
                        relative_path = file_path.relative_to(local_path)
                        remote_file_path = f"{remote_path}/{relative_path}".strip("/")
                        files_to_upload.append((file_path, remote_file_path))
            else:
                for file_path in local_path.iterdir():
                    if file_path.is_file():
                        remote_file_path = f"{remote_path}/{file_path.name}".strip("/")
                        files_to_upload.append((file_path, remote_file_path))

            # Upload files concurrently
            upload_tasks: list[Coroutine[None, None, Any]] = []
            for local_file_path, remote_file_path in files_to_upload:
                file_size = local_file_path.stat().st_size
                use_multipart = enable_multipart or file_size >= multipart_threshold

                if use_multipart and file_size > chunk_size:
                    task = upload_multipart(
                        self,
                        local_file_path,
                        remote_file_path,
                        chunk_size,
                        max_parallel_uploads,
                    )
                else:
                    # TODO: download_weight
                    task = put(
                        self,
                        str(local_file_path),
                        str(remote_file_path),
                    )

                upload_tasks.append(task)

            await asyncio.gather(*upload_tasks)

        except Exception as e:
            raise IOError(f"Folder upload failed: {str(e)}") from e
    else:
        raise ValueError(f"Path is neither a file nor a directory: {local_path}")


async def put(
    self: "AsyncHyphaArtifact",
    lpath: str | list[str],
    rpath: str | list[str],
    recursive: bool = False,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    **kwargs: Any,
) -> None:
    """Copy file(s) from local filesystem to remote (artifact)."""
    await transfer(
        self,
        rpath=rpath,
        lpath=lpath,
        recursive=recursive,
        callback=callback,
        maxdepth=maxdepth,
        on_error=on_error,
        transfer_type="PUT",
    )


async def cp(
    self: "AsyncHyphaArtifact",
    path1: str,
    path2: str,
    on_error: OnError | None = None,
    **kwargs: Any,
) -> None:
    """Alias for copy method

    Parameters
    ----------
    path1: str
        Source path
    path2: str
        Destination path
    on_error: "raise" or "ignore", optional
        What to do if a file is not found
    **kwargs:
        Additional arguments passed to copy method

    Returns
    -------
    None
    """
    recursive = kwargs.pop("recursive", False)
    maxdepth = kwargs.pop("maxdepth", None)
    return await self.copy(
        path1, path2, recursive=recursive, maxdepth=maxdepth, on_error=on_error
    )


async def head(self: "AsyncHyphaArtifact", path: str, size: int = 1024) -> bytes:
    """Get the first bytes of a file

    Parameters
    ----------
    path: str
        Path to the file
    size: int
        Number of bytes to read

    Returns
    -------
    bytes
        First bytes of the file
    """
    async with self.open(path, "rb") as f:
        result = await f.read(size)
        if isinstance(result, bytes):
            return result
        elif isinstance(result, str):
            return result.encode()
        else:
            return bytes(result)
