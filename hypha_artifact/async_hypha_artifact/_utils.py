"""Utility functions for async hypha artifact."""

from __future__ import annotations

import os
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
)

import httpx

from ..classes import StatusMessage, TransferPaths
from ..utils import OnError

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact
    from ..classes import ArtifactItem


async def walk_dir(
    self: "AsyncHyphaArtifact",
    current_path: str,
    maxdepth: int | None,
    withdirs: bool,
    current_depth: int,
) -> dict[str, ArtifactItem]:
    """Recursively walk a directory."""
    results: dict[str, ArtifactItem] = {}

    try:
        items = await self.ls(current_path)
    except (FileNotFoundError, IOError, httpx.RequestError):
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
                self, str(subdir_path), maxdepth, withdirs, current_depth + 1
            )
            results.update(subdirectory_results)

    return results


async def get_single_file(
    self: "AsyncHyphaArtifact",
    src_path: str,
    dst_path: str,
) -> None:
    """Copy a single file from remote to local."""
    local_dir = os.path.dirname(dst_path)
    if local_dir:
        os.makedirs(local_dir, exist_ok=True)

    async with self.open(src_path, "rb") as remote_file:
        content = await remote_file.read()

    content_bytes = content.encode("utf-8") if isinstance(content, str) else content

    with open(dst_path, "wb") as local_file:
        local_file.write(content_bytes)


async def put_single_file(
    self: "AsyncHyphaArtifact",
    src_path: str,
    dst_path: str,
) -> None:
    """Copy a single file from local to remote."""
    with open(src_path, "rb") as local_file:
        content = local_file.read()

    async with self.open(dst_path, "wb") as remote_file:
        await remote_file.write(content)


async def transfer_single_file(
    self: "AsyncHyphaArtifact",
    src_path: str,
    dst_path: str,
    callback: None | Callable[[dict[str, Any]], None] = None,
    on_error: OnError = "raise",
    current_file_index: int = 0,
    total_files: int = 1,
    transfer_type: Literal["PUT", "GET"] = "PUT",
) -> None:
    """Transfer a single file with status updates."""
    method_name = "upload" if transfer_type == "PUT" else "download"
    status_message = StatusMessage(method_name, total_files)

    if callback:
        callback(status_message.in_progress(src_path, current_file_index))

    try:
        if transfer_type == "PUT":
            await put_single_file(self, src_path=src_path, dst_path=dst_path)
        elif transfer_type == "GET":
            await get_single_file(self, dst_path=dst_path, src_path=src_path)

        if callback:
            callback(status_message.success(src_path))
    except (FileNotFoundError, IOError, httpx.RequestError) as e:
        if callback:
            callback(status_message.error(src_path, str(e)))
        if on_error == "raise":
            raise e


def local_find(
    src_path: str,
    maxdepth: int | None = None,
) -> list[str]:
    """Find all files in a local directory."""
    files: list[str] = []
    for root, _, dir_files in os.walk(src_path):
        if maxdepth is not None:
            rel_path = Path(root).relative_to(src_path)
            if len(rel_path.parts) >= maxdepth:
                continue
        for file_name in dir_files:
            files.append(str(Path(root) / file_name))

    return files


def get_transfer_paths(
    lpath: str,
    rpath: str,
    transfer_type: Literal["PUT", "GET"],
) -> TransferPaths:
    """Get source and destination paths based on transfer type."""
    if transfer_type == "GET":
        return TransferPaths(src=rpath, dst=lpath)

    return TransferPaths(src=lpath, dst=rpath)


async def prepare_recursive_transfer(
    self: "AsyncHyphaArtifact",
    paths: TransferPaths,
    maxdepth: int | None,
    transfer_type: Literal["PUT", "GET"],
) -> list[tuple[str, str]]:
    """Prepare a list of file transfers for recursive operations."""
    files: list[str] = []
    file_pairs: list[tuple[str, str]] = []
    os.makedirs(paths.dst, exist_ok=True)

    if transfer_type == "PUT":
        files = local_find(paths.src, maxdepth=maxdepth)

    if transfer_type == "GET":
        files = await self.find(paths.src, maxdepth=maxdepth, withdirs=False)

    for f in files:
        rel = Path(f).relative_to(paths.src)
        file_pairs.append((f, str(Path(paths.dst) / rel)))

    return file_pairs


async def prepare_transfer(
    self: "AsyncHyphaArtifact",
    lpath: str,
    rpath: str,
    recursive: bool,
    maxdepth: int | None,
    transfer_type: Literal["PUT", "GET"],
) -> list[tuple[str, str]]:
    """Prepare a list of file transfers."""
    paths: TransferPaths = get_transfer_paths(
        lpath=lpath, rpath=rpath, transfer_type=transfer_type
    )

    if recursive:
        return await prepare_recursive_transfer(
            self,
            paths=paths,
            maxdepth=maxdepth,
            transfer_type=transfer_type,
        )

    return [(paths.src, paths.dst)]


async def _prepare_all_transfers(
    self: "AsyncHyphaArtifact",
    rpath: str | list[str],
    lpath: str | list[str],
    recursive: bool,
    maxdepth: int | None,
    transfer_type: Literal["PUT", "GET"],
) -> list[tuple[str, str]]:
    """Prepare all file transfers, handling both single and multiple paths."""
    if isinstance(rpath, list) and isinstance(lpath, list):
        if len(rpath) != len(lpath):
            raise ValueError("rpath and lpath must be lists of the same length")
        all_files: list[tuple[str, str]] = []
        for rp, lp in zip(rpath, lpath):
            all_files.extend(
                await prepare_transfer(
                    self,
                    rpath=rp,
                    lpath=lp,
                    recursive=recursive,
                    maxdepth=maxdepth,
                    transfer_type=transfer_type,
                )
            )
        return all_files
    elif isinstance(rpath, str) and isinstance(lpath, str):
        return await prepare_transfer(
            self,
            rpath=rpath,
            lpath=lpath,
            recursive=recursive,
            maxdepth=maxdepth,
            transfer_type=transfer_type,
        )
    else:
        raise TypeError(
            "rpath and lpath must be either both strings or both lists of strings"
        )


async def _execute_transfers(
    self: "AsyncHyphaArtifact",
    all_files: list[tuple[str, str]],
    callback: None | Callable[[dict[str, Any]], None],
    on_error: OnError,
    transfer_type: Literal["PUT", "GET"],
) -> None:
    """Execute all file transfers."""
    for i, (src, dst) in enumerate(all_files):
        await transfer_single_file(
            self,
            src_path=src,
            dst_path=dst,
            callback=callback,
            on_error=on_error,
            current_file_index=i,
            total_files=len(all_files),
            transfer_type=transfer_type,
        )


async def transfer(
    self: "AsyncHyphaArtifact",
    rpath: str | list[str],
    lpath: str | list[str],
    recursive: bool = False,
    callback: None | Callable[[dict[str, Any]], None] = None,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    transfer_type: Literal["PUT", "GET"] = "PUT",
) -> None:
    """Copy file(s) between remote and local."""
    all_files = await _prepare_all_transfers(
        self, rpath, lpath, recursive, maxdepth, transfer_type
    )
    await _execute_transfers(self, all_files, callback, on_error, transfer_type)


async def copy_single_file(self: "AsyncHyphaArtifact", src: str, dst: str) -> None:
    """Copy a single file within the artifact."""
    async with self.open(src, "rb") as src_file:
        content = await src_file.read()

    async with self.open(dst, "wb") as dst_file:
        await dst_file.write(content)
