"""Multipart upload utilities."""

from __future__ import annotations

import asyncio
import math
import typing
from pathlib import Path
from typing import TYPE_CHECKING

from hypha_artifact.async_hypha_artifact._remote_methods import ArtifactMethod
from hypha_artifact.async_hypha_artifact._utils import (
    check_errors,
    clean_params,
    get_headers,
    get_method_url,
    remote_file_or_dir,
)
from hypha_artifact.async_hypha_artifact.types import (
    CompletedPart,
    CompleteMultipartParams,
    MultipartConfig,
    MultipartStatusMessage,
    PreparedPartInfo,
    StartMultipartParams,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from hypha_artifact.async_hypha_artifact import AsyncHyphaArtifact
    from hypha_artifact.classes import (
        MultipartUpload,
        OnError,
        ProgressEvent,
        StatusMessage,
        UploadPartServerInfo,
    )

MAXIMUM_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB
DEFAULT_CHUNK_SIZE = 6 * 1024 * 1024  # 6 MB
MINIMUM_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


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


def should_use_multipart(
    local_path: Path,
    multipart_config: MultipartConfig | None = None,
) -> bool:
    """Determine if multipart upload should be used."""
    file_size = local_path.stat().st_size

    if file_size > MAXIMUM_MULTIPART_THRESHOLD:
        return True

    if not multipart_config:
        return False

    chunk_size = multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE)

    if file_size < chunk_size:
        return False

    threshold = multipart_config.get("threshold")

    if threshold and file_size >= threshold:
        return True

    return bool(multipart_config.get("enable", False))


def validate_chunk_size(
    chunk_size: int,
) -> None:
    """Handle input errors for multipart upload.

    Args:
        chunk_size (int): The chunk size for the upload.

    Raises:
        ValueError: If the input parameters are invalid.

    """
    if chunk_size < MINIMUM_CHUNK_SIZE:
        error_msg = (
            "Chunk size must be greater than"
            f" {MINIMUM_CHUNK_SIZE // (1024 * 1024)}"
            "MB for multipart upload"
        )
        raise ValueError(error_msg)


async def start_multipart_upload(
    self: AsyncHyphaArtifact,
    local_path: Path,
    remote_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    download_weight: float = 1.0,
) -> MultipartUpload:
    """Start a multipart upload for a file."""
    chunk_size = min(chunk_size, MAXIMUM_MULTIPART_THRESHOLD)
    file_size = local_path.stat().st_size
    validate_chunk_size(chunk_size)
    part_count = math.ceil(file_size / chunk_size)

    start_params = StartMultipartParams(
        artifact_id=self.artifact_id,
        file_path=remote_path,
        part_count=part_count,
        download_weight=download_weight,
        use_proxy=self.use_proxy,
        use_local_url=self.use_local_url,
    )
    start_params = clean_params(start_params)

    start_url = get_method_url(self, ArtifactMethod.PUT_FILE_START_MULTIPART)
    start_resp = await self.get_client().post(
        start_url,
        headers=get_headers(self),
        json=dict(start_params),
    )
    check_errors(start_resp)
    return typing.cast("MultipartUpload", start_resp.json())


async def upload_part(
    self: AsyncHyphaArtifact,
    part_info: PreparedPartInfo,
) -> CompletedPart:
    """Upload a single part."""
    part_number = part_info["part_number"]
    upload_url = part_info["url"]

    async with self.open(upload_url, "wb") as f:
        await f.write(part_info["chunk"])

    etag = f.etag

    if etag is None:
        error_msg = "Failed to retrieve ETag from response"
        raise ValueError(error_msg)

    # Get ETag from response
    return CompletedPart(part_number=part_number, etag=etag)


async def upload_with_callback(
    self: AsyncHyphaArtifact,
    semaphore: asyncio.Semaphore,
    pinfo: PreparedPartInfo,
    callback: Callable[[ProgressEvent], None] | None,
    mpm: MultipartStatusMessage | None = None,
) -> CompletedPart:
    if callback and mpm:
        callback(mpm.part_info(pinfo["part_number"], pinfo.get("part_size")))
    try:
        async with semaphore:
            res = await upload_part(self, pinfo)
    except Exception as e:
        if callback and mpm:
            callback(mpm.part_error(pinfo["part_number"], str(e)))
        raise
    else:
        if callback and mpm:
            callback(mpm.part_success(pinfo["part_number"], pinfo.get("part_size")))
        return res


async def upload_parts(
    self: AsyncHyphaArtifact,
    local_path: Path,
    chunk_size: int,
    parts: list[UploadPartServerInfo],
    max_parallel_uploads: int,
    *,
    callback: Callable[[ProgressEvent], None] | None = None,
    file_path: str | None = None,
) -> list[CompletedPart]:
    """Upload parts of a file in parallel."""
    chunks = read_chunks(local_path, chunk_size)
    enumerate_parts = enumerate(list(zip(parts, chunks, strict=False)))
    parts_info: list[PreparedPartInfo] = [
        {
            "chunk": chunk,
            "url": part_info["url"],
            "part_number": part_info.get("part_number", index + 1),
            "part_size": len(chunk),
        }
        for index, (part_info, chunk) in enumerate_parts
    ]

    semaphore = asyncio.Semaphore(max_parallel_uploads)
    mpm = (
        MultipartStatusMessage("upload", file_path or str(local_path), len(parts_info))
        if callback is not None
        else None
    )

    upload_tasks = [
        upload_with_callback(self, semaphore, part_info, callback=callback, mpm=mpm)
        for part_info in parts_info
    ]

    return await asyncio.gather(*upload_tasks)


async def complete_multipart_upload(
    self: AsyncHyphaArtifact,
    upload_id: str,
    completed_parts: list[CompletedPart],
) -> None:
    """Complete a multipart upload."""
    simple_params = CompleteMultipartParams(
        artifact_id=self.artifact_id,
        upload_id=upload_id,
        parts=completed_parts,
    )
    complete_params = clean_params(simple_params)
    complete_url = get_method_url(self, ArtifactMethod.PUT_FILE_COMPLETE_MULTIPART)
    complete_resp = await self.get_client().post(
        complete_url,
        json=complete_params,
        headers=get_headers(self),
    )
    check_errors(complete_resp)


def get_multipart_settings(
    multipart_config: MultipartConfig | None = None,
) -> tuple[int, int]:
    """Get the default multipart settings."""
    if multipart_config is None:
        return DEFAULT_CHUNK_SIZE, 4

    chunk_size = multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE)
    max_parallel_uploads = multipart_config.get("max_parallel_uploads", 4)

    return chunk_size, max_parallel_uploads


async def upload_multipart(
    self: AsyncHyphaArtifact,
    local_path: Path,
    remote_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    max_parallel_uploads: int = 4,
    download_weight: float = 1.0,
    *,
    callback: Callable[[ProgressEvent], None] | None = None,
) -> None:
    """Upload a file using multipart upload with parallel uploads."""
    multipart_info = await start_multipart_upload(
        self,
        local_path,
        remote_path,
        chunk_size=chunk_size,
        download_weight=download_weight,
    )

    if "parts" not in multipart_info:
        error_msg = "Failed to start multipart upload."
        raise ValueError(error_msg)

    parts: list[UploadPartServerInfo] = multipart_info["parts"]
    completed_parts = await upload_parts(
        self,
        local_path,
        chunk_size,
        parts,
        max_parallel_uploads,
        callback=callback,
        file_path=str(local_path),
    )

    upload_id = multipart_info["upload_id"]
    await complete_multipart_upload(self, upload_id, completed_parts)


async def upload_multipart_files_loop(
    artifact: AsyncHyphaArtifact,
    files: list[tuple[str, str]],
    callback: Callable[[ProgressEvent], None] | None,
    status_message: StatusMessage,
    start_index: int,
    on_error: OnError,
    multipart_config: MultipartConfig | None,
) -> None:
    """Loop through files and upload them using multipart strategy."""
    chunk_size, max_parallel_uploads = get_multipart_settings(multipart_config)

    for i, (local_path, remote_path) in enumerate(files):
        current_file_index = start_index + i
        if callback:
            callback(status_message.in_progress(local_path, current_file_index))

        fixed_remote_path = remote_file_or_dir(local_path, remote_path)

        try:
            await upload_multipart(
                artifact,
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

        if callback:
            callback(status_message.success(local_path))
