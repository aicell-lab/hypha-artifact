"""Utility functions for async hypha artifact."""

from __future__ import annotations

import asyncio
import json
import math
import os
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from hypha_artifact.async_hypha_artifact._remote_methods import ArtifactMethod

if TYPE_CHECKING:
    from hypha_artifact.classes import ArtifactItem, JsonType

    from . import AsyncHyphaArtifact

DEFAULT_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB
DEFAULT_CHUNK_SIZE = 6 * 1024 * 1024  # 6 MB


async def get_existing_url(urlpath: str) -> str:
    return urlpath


async def get_read_url(artifact: AsyncHyphaArtifact, params: dict[str, Any]) -> str:
    response = await artifact.get_client().get(
        get_method_url(artifact, ArtifactMethod.GET_FILE),
        params=params,
        headers=get_headers(artifact),
        timeout=20,
    )

    check_errors(response)

    return response.content.decode().strip('"')


async def get_write_url(artifact: AsyncHyphaArtifact, params: dict[str, Any]) -> str:
    response = await artifact.get_client().post(
        get_method_url(artifact, ArtifactMethod.PUT_FILE),
        json=params,
        headers=get_headers(artifact),
        timeout=20,
    )

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
        items = await self.ls(current_path, version=version)
    except (OSError, FileNotFoundError, httpx.RequestError):
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
    with Path(src_path).open("rb") as local_file:
        content = local_file.read()

    async with self.open(dst_path, "wb") as remote_file:
        await remote_file.write(content)


def local_walk(
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
        files.extend(str(Path(root) / file_name) for file_name in dir_files)

    return files


def rel_path_pairs(
    files: list[str],
    src_path: str,
    dst_path: str,
) -> list[tuple[str, str]]:
    file_pairs: list[tuple[str, str]] = []
    for f in files:
        rel = Path(f).relative_to(src_path)
        file_pairs.append((f, str(dst_path / rel)))

    return file_pairs


def ensure_equal_len(
    rpath: str | list[str],
    lpath: str | list[str],
) -> tuple[list[str], list[str]]:
    """Assert that two paths (or lists of paths) are of equal length.

    Args:
        rpath (str | list[str]): The remote path(s) to check.
        lpath (str | list[str]): The local path(s) to check.

    Raises:
        ValueError: If the lengths of the paths do not match.
        ValueError: If the types of the paths do not match.

    Returns:
        _type_: _description_

    """
    if isinstance(rpath, str) and isinstance(lpath, str):
        rpath = [rpath]
        lpath = [lpath]
    elif isinstance(rpath, list) and isinstance(lpath, list):
        if len(rpath) != len(lpath):
            error_msg = "Both rpath and lpath must be the same length."
            raise ValueError(
                error_msg,
            )
    else:
        error_msg = "Both rpath and lpath must be strings or lists of strings."
        raise TypeError(
            error_msg,
        )

    return rpath, lpath


async def upload_part(
    self: AsyncHyphaArtifact,
    part_info: dict[str, Any],
    chunk_data: bytes,
    index: int,
) -> dict[str, Any]:
    """Upload a single part."""
    part_number = part_info.get("part_number", index)
    upload_url = part_info["url"]

    async with self.open(upload_url, "wb") as f:
        await f.write(chunk_data)

    etag = f.etag

    # Get ETag from response
    return {"part_number": part_number, "etag": etag}


def read_chunks(
    file_path: Path,
    chunk_size: int,
) -> list[bytes]:
    """Read file in chunks."""
    chunks: list[bytes] = []
    with file_path.open("rb") as f:
        while True:
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            chunks.append(chunk_data)

    return chunks


async def upload_with_semaphore(
    self: AsyncHyphaArtifact,
    semaphore: asyncio.Semaphore,
    index: int,
    part_info: dict[str, Any],
    chunk_data: bytes,
) -> dict[str, Any]:
    async with semaphore:
        return await upload_part(self, part_info, chunk_data, index=index + 1)


async def upload_multipart_with_semaphore(
    self: AsyncHyphaArtifact,
    parts_info: list[dict[str, Any]],
    chunks: list[bytes],
    max_parallel_uploads: int,
) -> list[dict[str, Any]]:
    """Upload a part using a semaphore for concurrency control."""
    semaphore = asyncio.Semaphore(max_parallel_uploads)

    # Upload all parts in parallel
    return await asyncio.gather(
        *[
            upload_with_semaphore(self, semaphore, index, part_info, chunk)
            for index, (part_info, chunk) in enumerate(
                zip(parts_info, chunks, strict=False),
            )
        ],
    )


def should_use_multipart(file_size: int, multipart_config: dict[str, Any]) -> bool:
    """Determine if multipart upload should be used."""
    if not file_size > multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE):
        return False

    if multipart_config.get("enable"):
        return True

    return file_size >= multipart_config.get("threshold", DEFAULT_MULTIPART_THRESHOLD)


# TODO @hugokallander: Refactor, merge with normal transfer
async def upload_multipart(
    self: AsyncHyphaArtifact,
    local_path: Path,
    remote_path: str,
    multipart_config: dict[str, Any],
    download_weight: float = 1.0,
) -> None:
    """Upload a file using multipart upload with parallel uploads."""
    file_size = local_path.stat().st_size

    if not should_use_multipart(file_size, multipart_config):
        return

    chunk_size = multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE)
    five_mb = 5 * 1024 * 1024
    if chunk_size < five_mb:
        error_msg = "Chunk size must be greater than 5MB for multipart upload"
        raise ValueError(error_msg)
    part_count = math.ceil(file_size / chunk_size)

    params: dict[str, Any] = prepare_params(
        self,
        {
            "file_path": remote_path,
            "part_count": part_count,
            "download_weight": download_weight,
            "use_proxy": self.use_proxy,
            "use_local_url": self.use_local_url,
        },
    )

    url = get_method_url(self, ArtifactMethod.PUT_FILE_START_MULTIPART)

    response = await self.get_client().post(
        url,
        headers=get_headers(self),
        json=params,
    )

    check_errors(response)

    multipart_info = json.loads(response.content.decode())

    upload_id = multipart_info["upload_id"]
    parts_info = multipart_info["parts"]
    chunks = read_chunks(local_path, chunk_size)
    max_parallel_uploads = multipart_config.get("max_parallel_uploads", 4)

    completed_parts = await upload_multipart_with_semaphore(
        self,
        parts_info,
        chunks,
        max_parallel_uploads,
    )

    params2: dict[str, Any] = prepare_params(
        self,
        {
            "upload_id": upload_id,
            "parts": completed_parts,
        },
    )

    url2 = get_method_url(self, ArtifactMethod.PUT_FILE_COMPLETE_MULTIPART)

    response = await self.get_client().post(
        url2,
        json=params2,
        headers=get_headers(self),
    )

    check_errors(response)


def prepare_params(
    self: AsyncHyphaArtifact,
    params: dict[str, JsonType] | None = None,
) -> dict[str, JsonType]:
    """Extend parameters with artifact_id."""
    cleaned_params: dict[str, JsonType] = {
        k: v for k, v in (params or {}).items() if v is not None
    }
    cleaned_params["artifact_id"] = self.artifact_id
    return cleaned_params


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
        raise ValueError(error_msg)

    response.raise_for_status()
