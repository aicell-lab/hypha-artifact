"""Methods for file I/O operations."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any, overload
from urllib.parse import urlparse

import httpx

from hypha_artifact.async_artifact_file import AsyncArtifactHttpFile
from hypha_artifact.classes import OnError, StatusMessage

from ._utils import (
    build_local_to_remote_pairs,
    build_remote_to_local_pairs,
    decode_to_text,
    download_to_path,
    get_existing_url,
    get_read_url,
    get_write_url,
    params_get_file_url,
    prepare_params,
    rel_path_pairs,
    target_path_with_optional_slash,
    upload_file_simple,
    upload_multipart,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from . import AsyncHyphaArtifact


@overload
async def cat(
    self: AsyncHyphaArtifact,
    path: list[str],
    on_error: OnError = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> dict[str, str | None]: ...


@overload
async def cat(
    self: AsyncHyphaArtifact,
    path: str,
    on_error: OnError = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> str | None: ...


async def cat(
    self: AsyncHyphaArtifact,
    path: str | list[str],
    on_error: OnError = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> dict[str, str | None] | str | None:
    """Get file(s) content as string(s).

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance
    path: str or list of str
        File path(s) to get content from
    recursive: bool
        If True and path is a directory, get all files content
    on_error: "raise" or "ignore"
        What to do if a file is not found
    version: str | None = None
        The version of the artifact to get content from.
        By default, it uses the latest version.
        If you want to use a staged version, you can set it to "stage".

    Returns
    -------
    str or dict or None
        File contents as string if path is a string, dict of {path: content} if path is
        a list, or None if the file is not found and on_error is "ignore"

    """
    if isinstance(path, list):
        return {
            p: await self.cat(
                p,
                recursive=recursive,
                on_error=on_error,
                version=version,
            )
            for p in path
        }

    if recursive and await self.isdir(path):
        files = await self.find(path, withdirs=False, version=version)
        return {f: await self.cat(f, on_error=on_error, version=version) for f in files}

    try:
        async with self.open(path, "r", version=version) as f:
            content = await f.read()
            return decode_to_text(content)
    except (OSError, FileNotFoundError, httpx.RequestError) as e:
        if on_error == "ignore":
            return None
        raise OSError from e


def fsspec_open(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: str = "rb",
    content_type: str = "application/octet-stream",
    version: str | None = None,
) -> AsyncArtifactHttpFile:
    """Open a file for reading or writing.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance
    urlpath: str
        Path to the file within the artifact
    mode: str
        File mode, similar to 'r', 'rb', 'w', 'wb', 'a', 'ab'
    version: str | None = None
        The version of the artifact to read from or write to.
        By default, it uses the latest version.
        If you want to use a staged version, you can set it to "stage".
    content_type: str
        The content type of the file.

    Returns
    -------
    AsyncArtifactHttpFile
        A file-like object

    """
    get_file_params = params_get_file_url(
        file_path=urlpath,
        version=version,
        use_proxy=self.use_proxy,
        use_local_url=self.use_local_url,
    )
    params: dict[str, Any] = prepare_params(
        self,
        get_file_params,
    )

    if urlparse(urlpath).scheme in ["http", "https", "ftp"]:
        get_url_func = partial(get_existing_url, urlpath)
    elif "r" in mode:
        get_url_func = partial(get_read_url, self, params)
    elif "w" in mode or "a" in mode:
        get_url_func = partial(get_write_url, self, params)
    else:
        exception_msg = f"Unsupported mode: {mode}"
        raise ValueError(exception_msg)

    return AsyncArtifactHttpFile(
        url_func=get_url_func,
        mode=mode,
        name=str(urlpath),
        content_type=content_type,
        ssl=self.ssl,
    )


async def copy(
    self: AsyncHyphaArtifact,
    path1: str,
    path2: str,
    maxdepth: int | None = None,
    on_error: OnError | None = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> None:
    """Copy file(s) from path1 to path2 within the artifact.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance
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
    version: str | None = None
        The version of the artifact to copy from.
        By default, it uses the latest version.
        If you want to use a staged version, you can set it to "stage".

    """
    if recursive and await self.isdir(path1):
        files = await self.find(
            path1,
            maxdepth=maxdepth,
            withdirs=False,
            version=version,
            hide_keep=False,
        )
        src_dst_paths = rel_path_pairs(files, src_path=path1, dst_path=path2)
    else:
        src_dst_paths = [(path1, path2)]

    try:
        for src_path, dst_path in src_dst_paths:
            async with self.open(src_path, "rb", version=version) as src_file:
                content = await src_file.read()

            async with self.open(dst_path, "wb") as dst_file:
                await dst_file.write(content)
    except (OSError, FileNotFoundError, httpx.RequestError) as e:
        if on_error == "raise":
            raise OSError from e


async def get(
    self: AsyncHyphaArtifact,
    rpath: str | list[str],
    lpath: str | list[str] | None = None,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem."""
    all_file_pairs = await build_remote_to_local_pairs(
        self,
        rpath,
        lpath,
        recursive=recursive,
        maxdepth=maxdepth,
        version=version,
    )

    status_message = StatusMessage("download", len(all_file_pairs))

    for current_file_index, (remote_path, local_path) in enumerate(all_file_pairs):
        if callback:
            callback(status_message.in_progress(remote_path, current_file_index))
        fixed_local_path = target_path_with_optional_slash(remote_path, local_path)

        try:
            await download_to_path(
                self,
                remote_path,
                fixed_local_path,
                version=version,
            )
        except (OSError, FileNotFoundError, httpx.RequestError) as e:
            if callback:
                callback(status_message.error(remote_path, str(e)))
            if on_error == "raise":
                raise OSError from e

        if callback:
            callback(status_message.success(remote_path))


async def put(
    self: AsyncHyphaArtifact,
    lpath: str | list[str],
    rpath: str | list[str] | None = None,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    *,
    recursive: bool = False,
    multipart_config: dict[str, Any] | None = None,
) -> None:
    """Copy file(s) from local filesystem to remote (artifact)."""
    all_file_pairs = build_local_to_remote_pairs(
        lpath,
        rpath,
        recursive=recursive,
        maxdepth=maxdepth,
    )

    status_message = StatusMessage("upload", len(all_file_pairs))

    for current_file_index, (local_path, remote_path) in enumerate(all_file_pairs):
        if callback:
            callback(status_message.in_progress(local_path, current_file_index))
        fixed_remote_path = target_path_with_optional_slash(local_path, remote_path)

        try:
            if multipart_config:
                await upload_multipart(
                    self,
                    Path(local_path),
                    fixed_remote_path,
                    multipart_config,
                )
            else:
                await upload_file_simple(self, local_path, fixed_remote_path)

        except (OSError, FileNotFoundError, httpx.RequestError) as e:
            if callback:
                callback(status_message.error(local_path, str(e)))
            if on_error == "raise":
                raise OSError from e

        if callback:
            callback(status_message.success(local_path))


async def cp(
    self: AsyncHyphaArtifact,
    path1: str,
    path2: str,
    on_error: OnError | None = None,
    maxdepth: int | None = None,
    version: str | None = None,
    *,
    recursive: bool = False,
) -> None:
    """Alias for copy method.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        Instance of the AsyncHyphaArtifact class
    path1: str
        Source path
    path2: str
        Destination path
    on_error: "raise" or "ignore", optional
        What to do if a file is not found
    maxdepth: int | None, optional
        Maximum depth to traverse for files
    recursive: bool = False, optional
        Whether to copy files recursively
    version: str | None = None, optional
        The version of the artifact to copy from.

    Returns
    -------
    None

    """
    return await self.copy(
        path1,
        path2,
        recursive=recursive,
        maxdepth=maxdepth,
        on_error=on_error,
        version=version,
    )


async def head(
    self: AsyncHyphaArtifact,
    path: str,
    size: int = 1024,
    version: str | None = None,
) -> bytes:
    """Get the first bytes of a file.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        Instance of the AsyncHyphaArtifact class
    path: str
        Path to the file
    size: int
        Number of bytes to read
    version: str | None = None
        The version of the artifact to get content from.
        By default, it uses the latest version.
        If you want to use a staged version, you can set it to "stage".

    Returns
    -------
    bytes
        First bytes of the file

    """
    async with self.open(path, "rb", version=version) as f:
        result = await f.read(size)
        if isinstance(result, bytes):
            return result
        if isinstance(result, str):
            return result.encode()
        return bytes(result)
