"""Methods for file I/O operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    overload,
    Literal,
)

import httpx

from ..utils import OnError
from ..async_artifact_file import AsyncArtifactHttpFile
from ..classes import StatusMessage

from ._remote import remote_get_file_url, remote_put_file_url

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
                await _copy_single_file(self, src_path, str(dst_path))
            except (FileNotFoundError, IOError, httpx.RequestError) as e:
                if on_error == "raise":
                    raise e
    else:
        await _copy_single_file(self, path1, path2)


async def _get_single_file(
    self: "AsyncHyphaArtifact",
    remote_path: str,
    local_path: str,
) -> None:
    """Helper method to copy a single file from remote to local."""
    local_dir = os.path.dirname(local_path)
    if local_dir:
        os.makedirs(local_dir, exist_ok=True)

    async with self.open(remote_path, "rb") as remote_file:
        content = await remote_file.read()

    content_bytes = content.encode("utf-8") if isinstance(content, str) else content

    with open(local_path, "wb") as local_file:
        local_file.write(content_bytes)


async def _put_single_file(
    self: "AsyncHyphaArtifact",
    local_path: str,
    remote_path: str,
) -> None:
    """Helper method to copy a single file from local to remote."""
    with open(local_path, "rb") as local_file:
        content = local_file.read()

    async with self.open(remote_path, "wb") as remote_file:
        await remote_file.write(content)


async def _transfer_single_file(
    self: "AsyncHyphaArtifact",
    local_path: str,
    remote_path: str,
    callback: None | Callable[[dict[str, Any]], None] = None,
    on_error: OnError = "raise",
    current_file_index: int = 0,
    total_files: int = 1,
    transfer_type: Literal["PUT", "GET"] = "PUT",
) -> None:
    """Helper method to copy a single file from local to remote."""
    method_name = "upload" if transfer_type == "PUT" else "download"
    status_message = StatusMessage(method_name, total_files)

    if callback:
        callback(status_message.in_progress(local_path, current_file_index))

    try:
        if transfer_type == "PUT":
            await _put_single_file(self, local_path, remote_path)
        elif transfer_type == "GET":
            await _get_single_file(self, remote_path, local_path)

        if callback:
            callback(status_message.success(local_path))
    except (FileNotFoundError, IOError, httpx.RequestError) as e:
        if callback:
            callback(status_message.error(local_path, str(e)))
        if on_error == "raise":
            raise e


async def _prepare_transfer(
    self: "AsyncHyphaArtifact",
    src_path: str,
    dst_path: str,
    recursive: bool,
    maxdepth: int | None,
    transfer_type: Literal["PUT", "GET"],
) -> list[tuple[str, str]]:
    """Prepare a list of file transfers."""
    files: list[str] = []
    if recursive and transfer_type == "PUT":
        os.makedirs(dst_path, exist_ok=True)
        for root, _, dir_files in os.walk(src_path):
            if maxdepth is not None:
                rel_path = Path(root).relative_to(src_path)
                if len(rel_path.parts) >= maxdepth:
                    continue
            for file_name in dir_files:
                files.append(str(Path(root) / file_name))

    if recursive and transfer_type == "GET":
        os.makedirs(dst_path, exist_ok=True)
        files = await self.find(src_path, maxdepth=maxdepth, withdirs=False)

    file_pairs: list[tuple[str, str]] = []
    if recursive:
        for f in files:
            rel = Path(f).relative_to(src_path)
            file_pairs.append((f, str(Path(dst_path) / rel)))
    else:
        file_pairs.append((src_path, dst_path))

    return file_pairs


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
    if isinstance(rpath, list) and isinstance(lpath, list):
        if len(rpath) != len(lpath):
            raise ValueError("rpath and lpath must be lists of the same length")
        all_files: list[tuple[str, str]] = []
        for rp, lp in zip(rpath, lpath):
            all_files.extend(
                await _prepare_transfer(
                    self, rp, lp, recursive, maxdepth, transfer_type="GET"
                )
            )
    elif isinstance(rpath, str) and isinstance(lpath, str):
        all_files = await _prepare_transfer(
            self, rpath, lpath, recursive, maxdepth, transfer_type="GET"
        )
    else:
        raise TypeError(
            "rpath and lpath must be either both strings or both lists of strings"
        )

    for i, (rp, lp) in enumerate(all_files):
        await _transfer_single_file(
            self,
            local_path=lp,
            remote_path=rp,
            callback=callback,
            on_error=on_error,
            current_file_index=i,
            total_files=len(all_files),
            transfer_type="GET",
        )


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
    if isinstance(lpath, list) and isinstance(rpath, list):
        if len(lpath) != len(rpath):
            raise ValueError("lpath and rpath must be lists of the same length")
        all_files: list[tuple[str, str]] = []
        for lp, rp in zip(lpath, rpath):
            all_files.extend(
                await _prepare_transfer(
                    self, lp, rp, recursive, maxdepth, transfer_type="PUT"
                )
            )
    elif isinstance(lpath, str) and isinstance(rpath, str):
        all_files = await _prepare_transfer(
            self, lpath, rpath, recursive, maxdepth, transfer_type="PUT"
        )
    else:
        raise TypeError(
            "lpath and rpath must be either both strings or both lists of strings"
        )

    for i, (lp, rp) in enumerate(all_files):
        await _transfer_single_file(
            self,
            local_path=lp,
            remote_path=rp,
            callback=callback,
            on_error=on_error,
            current_file_index=i,
            total_files=len(all_files),
            transfer_type="PUT",
        )


async def _copy_single_file(self: "AsyncHyphaArtifact", src: str, dst: str) -> None:
    """Helper method to copy a single file"""
    async with self.open(src, "rb") as src_file:
        content = await src_file.read()

    async with self.open(dst, "wb") as dst_file:
        await dst_file.write(content)


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
