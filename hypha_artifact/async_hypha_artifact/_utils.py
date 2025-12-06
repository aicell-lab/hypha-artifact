"""Utility functions for async hypha artifact."""

from __future__ import annotations

import asyncio
import math
import os
from http import HTTPStatus
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Protocol,
    Self,
    TypedDict,
    TypeVar,
    runtime_checkable,
)
from urllib.parse import urlparse

import anyio
import httpx

from hypha_artifact.async_hypha_artifact._remote_methods import ArtifactMethod
from hypha_artifact.classes import (
    MultipartConfig,
    MultipartStatusMessage,
    MultipartUpload,
    ProgressEvent,
    UploadPartServerInfo,
)
from hypha_artifact.utils import ensure_equal_len, local_walk, rel_path_pairs

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from types import TracebackType

    from _typeshed import OpenBinaryMode, OpenTextMode

    from hypha_artifact.classes import ArtifactItem

    from . import AsyncHyphaArtifact

MAXIMUM_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB
DEFAULT_CHUNK_SIZE = 6 * 1024 * 1024  # 6 MB
MINIMUM_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB

T = TypeVar("T")


@runtime_checkable
class AsyncBinaryFile(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def read(self) -> bytes: ...
    async def write(self, data: bytes) -> int: ...
    async def close(self) -> None: ...


class SyncBinaryFile(Protocol):
    def read(self, size: int = ...) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def close(self) -> None: ...


class ListChildrenParams(TypedDict):
    parent_id: str
    keywords: list[str] | None
    filters: Mapping[str, object] | None
    mode: str | None
    offset: int | None
    limit: int | None
    order_by: str | None
    silent: bool | None
    stage: bool | None


class CreateParams(TypedDict):
    alias: str
    workspace: str | None
    parent_id: str | None
    type: str | None
    manifest: Mapping[str, object] | None
    config: Mapping[str, object] | None
    version: str | None
    stage: bool | None
    comment: str | None
    secrets: Mapping[str, str] | None
    overwrite: bool | None


class ArtifactIdParams(TypedDict):
    artifact_id: str


class ListFilesParams(ArtifactIdParams):
    dir_path: str
    limit: int | None
    version: str | None


class GetFileUrlParams(ArtifactIdParams):
    file_path: str
    version: str | None
    use_proxy: bool | None
    use_local_url: bool | str | None


class RemoveFileParams(ArtifactIdParams):
    file_path: str


class StartMultipartParams(ArtifactIdParams):
    file_path: str
    part_count: int
    download_weight: float | None
    use_proxy: bool | None
    use_local_url: bool | str | None


class CompleteMultipartParams(ArtifactIdParams):
    upload_id: str
    parts: Sequence[CompletedPart]


class EditParams(ArtifactIdParams):
    manifest: Mapping[str, object] | None
    type: str | None
    config: Mapping[str, object] | None
    secrets: Mapping[str, str] | None
    version: str | None
    comment: str | None
    stage: bool | None


class CommitParams(ArtifactIdParams):
    version: str | None
    comment: str | None


class DeleteParams(ArtifactIdParams):
    delete_files: bool | None
    recursive: bool | None
    version: str | None


class PreparedPartInfo(TypedDict):
    """Client-prepared part info with data to upload."""

    url: str
    part_number: int
    chunk: bytes
    part_size: int


class CompletedPart(TypedDict):
    """Completed part info used to finalize multipart upload."""

    part_number: int
    etag: str


async def remote_file_or_dir(
    self: AsyncHyphaArtifact,
    src_path: str,
    dst_path: str,
) -> str:
    """Resolve remote destination semantics with explicit hint or remote check.

    - If `dst_path` ends with a path separator, treat as directory and append basename.
    - Else, if the remote `dst_path` currently exists as a directory, append basename.
    - Otherwise, treat `dst_path` as the full target path.
    """
    if str(dst_path).endswith(("/", os.sep)):
        return str(Path(dst_path) / Path(src_path).name)
    is_remote_dir = await self.isdir(dst_path)
    return str(Path(dst_path) / Path(src_path).name) if is_remote_dir else str(dst_path)


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
    _lf = await anyio.open_file(src_path, "rb")
    async with _lf as local_file:
        content = await local_file.read()

    async with self.open(dst_path, "wb") as remote_file:
        await remote_file.write(content)


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
        file_size (int): The size of the local file in bytes.
        chunk_size (int): The chunk size for the upload.
        multipart_config (dict[str, object]): The multipart configuration.

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
    return MultipartUpload(**start_resp.json())


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
    """Upload parts of a file in parallel.

    Args:
        self (AsyncHyphaArtifact): The artifact instance.
        local_path (Path): The local file path.
        chunk_size (int): The size of each chunk.
        parts (list[dict[str, object]]): The list of parts to upload.
        max_parallel_uploads (int): Maximum number of concurrent part uploads.
        callback (Callable[[dict[str, object]], None] | None):
            Optional progress callback invoked for each part with multipart
            status messages.
        file_path (str | None): Optional path used to annotate status messages.

    Returns:
        list[dict[str, object]]: The list of responses from the uploaded parts.

    """
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
    """Complete a multipart upload.

    Args:
        self (AsyncHyphaArtifact): The artifact instance.
        upload_id (str): The ID of the upload.
        completed_parts (list[dict[str, object]]): The list of completed parts.

    """
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

    parts = multipart_info["parts"]
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
