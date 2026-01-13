"""Utility functions for async hypha artifact."""

from __future__ import annotations

import asyncio
import os
import typing
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urlparse

import anyio
import httpx

from hypha_artifact.async_artifact_file import AsyncArtifactHttpFile
from hypha_artifact.async_hypha_artifact._remote_methods import ArtifactMethod
from hypha_artifact.async_hypha_artifact.types import GetFileUrlParams
from hypha_artifact.utils import ensure_equal_len, local_walk, rel_path_pairs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from _typeshed import OpenBinaryMode, OpenTextMode

    from hypha_artifact.classes import (
        ArtifactItem,
        OnError,
        ProgressEvent,
        StatusMessage,
    )

    from . import AsyncHyphaArtifact

T = TypeVar("T")


def remote_file_or_dir(
    src_path: str,
    dst_path: str,
) -> str:
    """Resolve remote destination semantics without remote check.

    - If `dst_path` ends with a path separator, treat as directory and append basename.
    - Otherwise, treat `dst_path` as the full target path.
    """
    if str(dst_path).endswith(("/", os.sep)):
        return str(Path(dst_path) / Path(src_path).name)
    return str(dst_path)


def filter_by_name(
    files: list[ArtifactItem],
    name: str,
) -> list[ArtifactItem]:
    """Filter files by name."""
    return [f for f in files if Path(f["name"]).name == Path(name).name]


async def download_to_path(
    self: AsyncHyphaArtifact,
    remote_path: str,
    local_path: str,
    *,
    version: str | None = None,
) -> None:
    parent = Path(local_path).parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
    async with self.open(remote_path, "rb", version=version) as src_file:
        data = await src_file.read()
    pre_dst_file = await anyio.open_file(local_path, "wb")
    async with pre_dst_file as dst_file:
        await dst_file.write(data)


async def upload_file_simple(
    self: AsyncHyphaArtifact,
    local_path: str | Path,
    remote_path: str,
) -> None:
    pre_src_file = await anyio.open_file(local_path, "rb")
    async with pre_src_file as src_file:
        data = await src_file.read()
    async with self.open(remote_path, "wb") as dst_file:
        await dst_file.write(data)


async def get_upload_urls(
    artifact: AsyncHyphaArtifact,
    file_paths: list[str],
    version: str | None = None,
) -> dict[str, str]:
    """Get upload URLs for a list of files."""
    params = GetFileUrlParams(
        artifact_id=artifact.artifact_id,
        file_path=file_paths,
        version=version,
        use_proxy=artifact.use_proxy,
        use_local_url=artifact.use_local_url,
    )
    clean = clean_params(params)

    response = await artifact.get_client().post(
        get_method_url(artifact, ArtifactMethod.PUT_FILE),
        json=clean,
        headers=get_headers(artifact),
        timeout=60,
    )
    check_errors(response)
    # Assume response is Dict[str, str] mapping path -> url
    return response.json()


async def _upload_single_file_with_url(
    artifact: AsyncHyphaArtifact,
    local_path: str,
    remote_path: str,
    url: str,
    index: int,
    semaphore: asyncio.Semaphore,
    callback: Callable[[ProgressEvent], None] | None,
    status_message: StatusMessage | None,
    on_error: OnError,
) -> None:
    async with semaphore:
        if callback and status_message:
            callback(status_message.in_progress(local_path, index))

        try:
            # Construct file object manually
            # NOTE: We assume 'wb' mode and artifact settings
            # We do NOT use self.open because we have the URL
            headers = dict(artifact.default_headers)

            # Create AsyncArtifactHttpFile directly
            file_obj = AsyncArtifactHttpFile(
                url=url,
                mode="wb",
                ssl=artifact.ssl,
                additional_headers=headers,
                name=remote_path,
            )

            async with file_obj as dst_file:
                pre_src_file = await anyio.open_file(local_path, "rb")
                async with pre_src_file as src:
                    data = await src.read()
                await dst_file.write(data)

            if callback and status_message:
                callback(status_message.success(local_path))

        except Exception as e:
            if callback and status_message:
                callback(status_message.error(local_path, str(e)))
            if on_error == "raise":
                raise OSError from e


async def upload_simple_files_batch(
    self: AsyncHyphaArtifact,
    file_pairs: list[tuple[str, str]],
    callback: Callable[[ProgressEvent], None] | None = None,
    status_message: StatusMessage | None = None,
    start_index: int = 0,
    on_error: OnError = "raise",
    version: str | None = None,
    max_concurrency: int = 10,
    batch_size: int = 500,
) -> None:
    """Upload multiple files concurrently."""
    if not file_pairs:
        return

    files_map = {remote_p: local_p for local_p, remote_p in file_pairs}
    all_remote_paths = list(files_map.keys())

    semaphore = asyncio.Semaphore(max_concurrency)

    for batch_start_index in range(0, len(all_remote_paths), batch_size):
        batch_rpaths = all_remote_paths[
            batch_start_index : batch_start_index + batch_size
        ]
        try:
            path_urls = await get_upload_urls(self, batch_rpaths, version=version)
        except Exception as e:
            if on_error == "raise":
                msg = f"Failed to get upload URLs: {e}"
                raise OSError(msg) from e
            continue

        tasks: list[typing.Awaitable[None]] = []
        for rpath_index, rpath in enumerate(batch_rpaths):
            if rpath in path_urls:
                lpath = files_map[rpath]
                idx = start_index + batch_start_index + rpath_index
                tasks.append(
                    _upload_single_file_with_url(
                        self,
                        lpath,
                        rpath,
                        path_urls[rpath],
                        idx,
                        semaphore,
                        callback,
                        status_message,
                        on_error,
                    ),
                )

        if tasks:
            await asyncio.gather(*tasks)


async def build_remote_to_local_pairs(
    self: AsyncHyphaArtifact,
    rpath: str | list[str],
    lpath: str | list[str] | None,
    *,
    recursive: bool,
    maxdepth: int | None,
    version: str | None,
) -> list[tuple[str, str]]:
    """Expand rpath/lpath into concrete (remote, local) file pairs.

    Applies recursive listing when asked and errors when a directory is passed
    without recursive flag.
    """
    if not lpath:
        lpath = rpath
    rpaths, lpaths = ensure_equal_len(rpath, lpath)
    pairs: list[tuple[str, str]] = []
    for rp, lp in zip(rpaths, lpaths, strict=False):
        if await self.isdir(rp, version=version):
            if not recursive:
                msg = f"Path is a directory: {rp}. Use --recursive to get directories."
                raise IsADirectoryError(msg)
            Path(lp).mkdir(parents=True, exist_ok=True)
            files = await self.find(
                rp,
                maxdepth=maxdepth,
                withdirs=False,
                version=version,
            )
            pairs.extend(rel_path_pairs(files, src_path=rp, dst_path=lp))
        else:
            pairs.append((rp, lp))
    return pairs


def build_local_to_remote_pairs(
    lpath: str | list[str],
    rpath: str | list[str] | None,
    *,
    recursive: bool,
    maxdepth: int | None,
) -> list[tuple[str, str]]:
    """Expand lpath/rpath into concrete (local, remote) file pairs."""
    if not rpath:
        rpath = lpath
    rpaths, lpaths = ensure_equal_len(rpath, lpath)
    pairs: list[tuple[str, str]] = []
    for rp, lp in zip(rpaths, lpaths, strict=False):
        if Path(lp).is_dir():
            if not recursive:
                msg = f"Path is a directory: {rp}. Use --recursive to put directories."
                raise IsADirectoryError(msg)
            files = local_walk(lp, maxdepth=maxdepth)
            pairs.extend(rel_path_pairs(files, src_path=lp, dst_path=rp))
        else:
            pairs.append((lp, rp))
    return pairs


async def get_url(
    artifact: AsyncHyphaArtifact,
    urlpath: str,
    mode: OpenBinaryMode | OpenTextMode,
    params: Mapping[str, object],
) -> str:
    """Get a URL for reading or writing a file."""
    if urlparse(urlpath).scheme in ["http", "https", "ftp"]:
        return urlpath
    is_read = ("r" in mode) or ("+" in mode)
    is_write = any(flag in mode for flag in ("w", "a", "x")) or ("+" in mode)

    if is_read and not is_write:
        response = await artifact.get_client().get(
            get_method_url(artifact, ArtifactMethod.GET_FILE),
            params=params,  # type: ignore[arg-type]
            headers=get_headers(artifact),
            timeout=60,
        )
    elif is_write:
        response = await artifact.get_client().post(
            get_method_url(artifact, ArtifactMethod.PUT_FILE),
            json=params,
            headers=get_headers(artifact),
            timeout=60,
        )
    else:
        exception_msg = f"Unsupported mode: {mode}"
        raise TypeError(exception_msg)

    check_errors(response)

    return response.content.decode().strip('"')


async def walk_dir(
    self: AsyncHyphaArtifact,
    current_path: str,
    maxdepth: int | None,
    current_depth: int,
    version: str | None = None,
    *,
    withdirs: bool,
) -> dict[str, ArtifactItem]:
    """Recursively walk a directory."""
    results: dict[str, ArtifactItem] = {}

    try:
        items = await self.ls(current_path, version=version, detail=True)
    except (OSError, httpx.RequestError):
        return {}

    for item in items:
        item_type = item["type"]
        item_name = item["name"]

        if item_type == "file" or (withdirs and item_type == "directory"):
            full_path = Path(current_path) / str(item_name)
            results[str(full_path)] = item

        if item_type == "directory" and (maxdepth is None or current_depth < maxdepth):
            subdir_path = Path(current_path) / str(item_name)
            subdirectory_results = await walk_dir(
                self,
                str(subdir_path),
                maxdepth,
                current_depth + 1,
                version=version,
                withdirs=withdirs,
            )
            results.update(subdirectory_results)

    return results


async def put_single_file(
    self: AsyncHyphaArtifact,
    src_path: str,
    dst_path: str,
) -> None:
    """Copy a single file from local to remote."""
    _lf = await anyio.open_file(src_path, "rb")
    async with _lf as local_file:
        content = await local_file.read()

    async with self.open(dst_path, "wb") as remote_file:
        await remote_file.write(content)


def clean_params(
    params: Mapping[str, object],
) -> dict[str, object]:
    """Return a plain dict of parameters with None values removed."""
    return {k: v for k, v in params.items() if v is not None}


def get_method_url(self: AsyncHyphaArtifact, method: ArtifactMethod) -> str:
    """Get the URL for a specific artifact method."""
    return f"{self.artifact_url}/{method}"


def get_headers(self: AsyncHyphaArtifact) -> dict[str, str]:
    """Get headers for HTTP requests.

    Returns:
        dict[str, str]: Headers to include in the request.

    """
    return {"Authorization": f"Bearer {self.token}"} if self.token else {}


def check_errors(response: httpx.Response) -> None:
    """Handle errors in HTTP responses."""
    if response.status_code != HTTPStatus.OK:
        error_msg = f"Unexpected error: {response.text}"
        raise httpx.RequestError(error_msg)

    response.raise_for_status()
