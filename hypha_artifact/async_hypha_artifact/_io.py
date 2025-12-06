"""Methods for file I/O operations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, overload

import httpx

from hypha_artifact.async_artifact_file import AsyncArtifactHttpFile
from hypha_artifact.classes import (
    MultipartConfig,
    OnError,
    ProgressEvent,
    StatusMessage,
)
from hypha_artifact.transfer_progress import TransferProgress
from hypha_artifact.utils import decode_to_text, local_file_or_dir, rel_path_pairs

from ._utils import (
    GetFileUrlParams,
    batch_get_upload_urls,
    build_local_to_remote_pairs,
    build_remote_to_local_pairs,
    clean_params,
    download_to_path,
    get_multipart_settings,
    get_url,
    remote_file_or_dir,
    should_use_multipart,
    upload_file_direct,
    upload_multipart,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from _typeshed import OpenBinaryMode, OpenTextMode

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
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _cat_one(p: str) -> tuple[str, str | None]:
            async with semaphore:
                content = await self.cat(
                    p,
                    recursive=recursive,
                    on_error=on_error,
                    version=version,
                )
                return (p, content)

        results = await asyncio.gather(*[_cat_one(p) for p in path])
        return dict(results)

    if recursive and await self.isdir(path):
        files = await self.find(path, withdirs=False, version=version)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _cat_file(f: str) -> tuple[str, str | None]:
            async with semaphore:
                content = await self.cat(f, on_error=on_error, version=version)
                return (f, content)

        results = await asyncio.gather(*[_cat_file(f) for f in files])
        return dict(results)

    try:
        async with self.open(path, "r", version=version) as f:
            content = await f.read()
            return decode_to_text(content)
    except (OSError, FileNotFoundError, httpx.RequestError) as e:
        if on_error == "ignore":
            return None
        raise OSError from e


@overload
def fsspec_open(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenTextMode = "r",
    content_type: str = "text/plain",
    version: str | None = None,
    *,
    additional_headers: Mapping[str, str] | None = None,
) -> AsyncArtifactHttpFile[str]: ...


@overload
def fsspec_open(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenBinaryMode,
    content_type: str = "application/octet-stream",
    version: str | None = None,
    *,
    additional_headers: Mapping[str, str] | None = None,
) -> AsyncArtifactHttpFile[bytes]: ...


def fsspec_open(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenBinaryMode | OpenTextMode = "r",
    content_type: str = "application/octet-stream",
    version: str | None = None,
    *,
    additional_headers: Mapping[str, str] | None = None,
) -> AsyncArtifactHttpFile[str] | AsyncArtifactHttpFile[bytes]:
    """Open a file for reading or writing.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance
    urlpath: str
        Path to the file within the artifact
    mode: OpenBinaryMode | OpenTextMode
        File mode, similar to 'r', 'rb', 'w', 'wb', 'a', 'ab'
    version: str | None = None
        The version of the artifact to read from or write to.
        By default, it uses the latest version.
        If you want to use a staged version, you can set it to "stage".
    content_type: str
        The content type of the file.
    additional_headers: Mapping[str, str] | None
        Optional headers to include for this file-open call. These are merged with
        the instance's default headers, with per-call values taking precedence.

    Returns
    -------
    AsyncArtifactHttpFile
        A file-like object

    """
    get_file_params = GetFileUrlParams(
        artifact_id=self.artifact_id,
        file_path=urlpath,
        version=version,
        use_proxy=self.use_proxy,
        use_local_url=self.use_local_url,
    )
    params = clean_params(get_file_params)

    async def _resolve_url() -> str:
        return await get_url(self, urlpath, mode, params)

    combined_headers = {**self.default_headers, **(additional_headers or {})}

    return AsyncArtifactHttpFile(
        url=None,
        mode=mode,
        name=str(urlpath),
        content_type=content_type,
        ssl=self.ssl,
        additional_headers=combined_headers,
        url_factory=_resolve_url,
        client=self.get_client(),
    )


@overload
async def get_file_url(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenTextMode,
    version: str | None = None,
) -> str: ...


@overload
async def get_file_url(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenBinaryMode,
    version: str | None = None,
) -> str: ...


async def get_file_url(
    self: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenBinaryMode | OpenTextMode,
    version: str | None = None,
) -> str:
    """Public helper to resolve a read/write URL for a file based on mode/version."""
    get_file_params = GetFileUrlParams(
        artifact_id=self.artifact_id,
        file_path=urlpath,
        version=version,
        use_proxy=self.use_proxy,
        use_local_url=self.use_local_url,
    )
    params = clean_params(get_file_params)
    return await get_url(self, urlpath, mode, params)


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

    semaphore = asyncio.Semaphore(self.max_concurrency)

    async def _copy_one(src_path: str, dst_path: str) -> None:
        async with semaphore:
            async with self.open(src_path, "rb", version=version) as src_file:
                content = await src_file.read()
            async with self.open(dst_path, "wb") as dst_file:
                await dst_file.write(content)

    try:
        await asyncio.gather(
            *[_copy_one(src, dst) for src, dst in src_dst_paths],
        )
    except Exception as e:
        if on_error == "raise":
            raise OSError from e


async def get(
    self: AsyncHyphaArtifact,
    rpath: str | list[str],
    lpath: str | list[str] | None = None,
    callback: None | Callable[[ProgressEvent], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    version: str | None = None,
    *,
    recursive: bool = False,
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        Instance of the AsyncHyphaArtifact class
    rpath: str or list of str
        Remote path(s) to copy from
    lpath: str or list of str | None
        Local path(s) to copy to
    callback: None | Callable[[ProgressEvent], None]
        Optional callback function to report progress
    maxdepth: int | None
        Maximum recursion depth
    on_error: OnError
        Error handling strategy
    version: str | None
        Version of the artifact to copy from
    recursive: bool
        Whether to copy directories recursively

    """
    all_file_pairs = await build_remote_to_local_pairs(
        self,
        rpath,
        lpath,
        recursive=recursive,
        maxdepth=maxdepth,
        version=version,
    )

    status_message = StatusMessage("download", len(all_file_pairs))
    callback = callback or TransferProgress("download")
    semaphore = asyncio.Semaphore(self.max_concurrency)
    completed_count = 0
    lock = asyncio.Lock()

    async def _download_one(
        remote_path: str,
        local_path: str,
    ) -> None:
        nonlocal completed_count
        async with lock:
            idx = completed_count
        if callback:
            callback(status_message.in_progress(remote_path, idx))
        fixed_local_path = local_file_or_dir(remote_path, local_path)

        try:
            async with semaphore:
                await download_to_path(
                    self,
                    remote_path,
                    fixed_local_path,
                    version=version,
                )
        except Exception as e:
            if callback:
                callback(status_message.error(remote_path, str(e)))
            if on_error == "raise":
                raise OSError from e
            return

        async with lock:
            completed_count += 1
        if callback:
            callback(status_message.success(remote_path))

    await asyncio.gather(
        *[_download_one(rp, lp) for rp, lp in all_file_pairs],
    )


async def put(
    self: AsyncHyphaArtifact,
    lpath: str | list[str],
    rpath: str | list[str] | None = None,
    callback: None | Callable[[ProgressEvent], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    *,
    recursive: bool = False,
    multipart_config: MultipartConfig | None = None,
) -> None:
    """Copy file(s) from local filesystem to remote (artifact).

    Parameters
    ----------
    self: AsyncHyphaArtifact
        Instance of the AsyncHyphaArtifact class
    lpath: str or list of str
        Local path(s) to copy from
    rpath: str or list of str | None
        Remote path(s) to copy to
    callback: None | Callable[[ProgressEvent], None]
        Optional callback function to report progress
    maxdepth: int | None
        Maximum recursion depth
    on_error: OnError
        Error handling strategy
    version: str | None
        Version of the artifact to copy to
    recursive: bool
        Whether to copy directories recursively
    multipart_config: MultipartConfig | None
        Configuration for multipart uploads, if applicable.

    """
    all_file_pairs = build_local_to_remote_pairs(
        lpath,
        rpath,
        recursive=recursive,
        maxdepth=maxdepth,
    )

    status_message = StatusMessage("upload", len(all_file_pairs))
    callback = callback or TransferProgress("upload")

    # Separate files into multipart and simple uploads
    simple_pairs: list[tuple[str, str]] = []
    multipart_pairs: list[tuple[str, str]] = []

    for local_path, remote_path in all_file_pairs:
        if should_use_multipart(Path(local_path), multipart_config):
            multipart_pairs.append((local_path, remote_path))
        else:
            simple_pairs.append((local_path, remote_path))

    completed_count = 0
    lock = asyncio.Lock()

    # For simple uploads, batch fetch all presigned URLs first, then upload
    if simple_pairs:
        # Resolve remote paths in parallel (handle directory semantics)
        async def _resolve_remote(
            local_path: str,
            remote_path: str,
        ) -> tuple[str, str]:
            fixed = await remote_file_or_dir(self, local_path, remote_path)
            return (local_path, fixed)

        resolved_pairs = list(
            await asyncio.gather(
                *[_resolve_remote(lp, rp) for lp, rp in simple_pairs],
            ),
        )

        # Batch fetch all presigned URLs in parallel
        remote_paths = [rp for _, rp in resolved_pairs]
        presigned_urls = await batch_get_upload_urls(self, remote_paths)

        # Upload all files in parallel using the pre-fetched URLs
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _upload_simple(
            local_path: str,
            presigned_url: str,
            idx: int,
        ) -> None:
            nonlocal completed_count
            if callback:
                callback(status_message.in_progress(local_path, idx))

            try:
                async with semaphore:
                    await upload_file_direct(
                        self.get_client(),
                        local_path,
                        presigned_url,
                    )
            except Exception as e:
                if callback:
                    callback(status_message.error(local_path, str(e)))
                if on_error == "raise":
                    raise OSError from e
                return

            async with lock:
                completed_count += 1
            if callback:
                callback(status_message.success(local_path))

        await asyncio.gather(
            *[
                _upload_simple(lp, url, i)
                for i, ((lp, _), url) in enumerate(
                    zip(resolved_pairs, presigned_urls, strict=True),
                )
            ],
        )

    # Handle multipart uploads separately (they have their own URL fetching)
    if multipart_pairs:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _upload_multipart(
            local_path: str,
            remote_path: str,
        ) -> None:
            nonlocal completed_count
            async with lock:
                idx = completed_count
            if callback:
                callback(status_message.in_progress(local_path, idx))

            try:
                async with semaphore:
                    fixed_remote_path = await remote_file_or_dir(
                        self,
                        local_path,
                        remote_path,
                    )
                    chunk_size, max_parallel_uploads = get_multipart_settings(
                        multipart_config,
                    )
                    await upload_multipart(
                        self,
                        Path(local_path),
                        fixed_remote_path,
                        chunk_size=chunk_size,
                        max_parallel_uploads=max_parallel_uploads,
                        callback=callback,
                    )
            except Exception as e:
                if callback:
                    callback(status_message.error(local_path, str(e)))
                if on_error == "raise":
                    raise OSError from e
                return

            async with lock:
                completed_count += 1
            if callback:
                callback(status_message.success(local_path))

        await asyncio.gather(
            *[_upload_multipart(lp, rp) for lp, rp in multipart_pairs],
        )


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
