"""Methods for file I/O operations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    overload,
)
from urllib.parse import urlparse

import httpx

from ..classes import StatusMessage, OnError
from ..async_artifact_file import AsyncArtifactHttpFile

from ._remote_methods import ArtifactMethod
from ._utils import (
    check_errors,
    copy_single_file,
    get_headers,
    local_walk,
    prepare_params,
    get_method_url,
    assert_equal_len,
    rel_path_pairs,
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
            content: str | bytes = await f.read()
            if isinstance(content, bytes):
                return content.decode("utf-8")
            if isinstance(content, (bytearray, memoryview)):
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
    if urlparse(urlpath).scheme in ["http", "https", "ftp"]:

        async def get_url():
            return urlpath

    elif "r" in mode:

        async def get_url():
            params: dict[str, Any] = prepare_params(
                self,
                {
                    "file_path": urlpath,
                    "use_proxy": self.use_proxy,
                    "use_local_url": self.use_local_url,
                },
            )

            response = await self.get_client().get(
                get_method_url(self, ArtifactMethod.GET_FILE),
                params=params,
                headers=get_headers(self),
                timeout=20,
            )

            check_errors(response)

            return response.content.decode().strip('"')

    elif "w" in mode or "a" in mode:

        async def get_url():
            params: dict[str, Any] = prepare_params(
                self,
                {
                    "file_path": urlpath,
                    "use_proxy": self.use_proxy,
                    "use_local_url": self.use_local_url,
                },
            )

            response = await self.get_client().post(
                get_method_url(self, ArtifactMethod.PUT_FILE),
                json=params,
                headers=get_headers(self),
                timeout=20,
            )

            check_errors(response)

            return response.content.decode().strip('"')

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
    lpath: str | list[str] | None = None,
    recursive: bool = False,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem."""
    if not lpath:
        lpath = rpath
    rpaths, lpaths = assert_equal_len(rpath, lpath)

    all_file_pairs: list[tuple[str, str]] = []
    for rp, lp in zip(rpaths, lpaths):
        if recursive:
            os.makedirs(lp, exist_ok=True)
            files = await self.find(rp, maxdepth=maxdepth, withdirs=False)
            file_pairs = rel_path_pairs(files, src_path=rp, dst_path=lp)
            all_file_pairs.extend(file_pairs)
        else:
            all_file_pairs.append((rp, lp))

    status_message = StatusMessage("download", len(all_file_pairs))

    for current_file_index, (remote_path, local_path) in enumerate(all_file_pairs):
        if callback:
            callback(status_message.in_progress(remote_path, current_file_index))

        try:
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)

            async with self.open(remote_path, "rb") as remote_file:
                content = await remote_file.read()

            content_bytes = (
                content.encode("utf-8") if isinstance(content, str) else content
            )

            with open(local_path, "wb") as local_file:
                local_file.write(content_bytes)
        except (FileNotFoundError, IOError, httpx.RequestError) as e:
            if callback:
                callback(status_message.error(remote_path, str(e)))
            if on_error == "raise":
                raise e

        if callback:
            callback(status_message.success(remote_path))


async def put(
    self: "AsyncHyphaArtifact",
    lpath: str | list[str],
    rpath: str | list[str] | None = None,
    recursive: bool = False,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    multipart_config: dict[str, Any] | None = None,
) -> None:
    """Copy file(s) from local filesystem to remote (artifact)."""
    if not rpath:
        rpath = lpath
    rpaths, lpaths = assert_equal_len(rpath, lpath)

    all_file_pairs: list[tuple[str, str]] = []
    for rp, lp in zip(rpaths, lpaths):
        if recursive:
            files = local_walk(lp, maxdepth=maxdepth)
            file_pairs = rel_path_pairs(files, src_path=lp, dst_path=rp)
            all_file_pairs.extend(file_pairs)
        else:
            all_file_pairs.append((lp, rp))

    status_message = StatusMessage("upload", len(all_file_pairs))

    for current_file_index, (local_path, remote_path) in enumerate(all_file_pairs):
        if callback:
            callback(status_message.in_progress(local_path, current_file_index))

        try:
            if multipart_config:
                await upload_multipart(
                    self,
                    Path(local_path),
                    remote_path,
                    multipart_config,
                )
            else:
                with open(local_path, "rb") as local_file:
                    content = local_file.read()

                async with self.open(remote_path, "wb") as remote_file:
                    await remote_file.write(content)

        except (FileNotFoundError, IOError, httpx.RequestError) as e:
            if callback:
                callback(status_message.error(local_path, str(e)))
            if on_error == "raise":
                raise e

        if callback:
            callback(status_message.success(local_path))


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
