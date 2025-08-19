"""Utility functions for async hypha artifact."""

from __future__ import annotations

import asyncio
import math
import os
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

import httpx

from hypha_artifact.async_hypha_artifact._remote_methods import ArtifactMethod

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hypha_artifact.classes import ArtifactItem

    from . import AsyncHyphaArtifact

DEFAULT_MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100 MB
DEFAULT_CHUNK_SIZE = 6 * 1024 * 1024  # 6 MB
MINIMUM_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB


class ListFilesParams(TypedDict, total=False):
    dir_path: str
    version: str


class GetFileUrlParams(TypedDict, total=False):
    file_path: str
    version: str
    use_proxy: bool
    use_local_url: bool | str


class RemoveFileParams(TypedDict, total=False):
    file_path: str


def params_list_files(
    dir_path: str = ".",
    version: str | None = None,
) -> ListFilesParams:
    """Typed builder for List Files parameters."""
    p: ListFilesParams = {"dir_path": dir_path}
    if version is not None:
        p["version"] = version
    return p


def params_get_file_url(
    file_path: str,
    *,
    version: str | None = None,
    use_proxy: bool | None = None,
    use_local_url: bool | str | None = None,
) -> GetFileUrlParams:
    """Typed builder for GET/PUT file URL params used by fsspec_open and uploads."""
    p: GetFileUrlParams = {"file_path": file_path}
    if version is not None:
        p["version"] = version
    if use_proxy is not None:
        p["use_proxy"] = use_proxy
    if use_local_url is not None:
        p["use_local_url"] = use_local_url
    return p


def params_remove_file(file_path: str) -> RemoveFileParams:
    return {"file_path": file_path}


def params_create(
    *,
    alias: str,
    workspace: str | None,
    parent_id: str | None,
    artifact_type: str | None,
    manifest: str | dict[str, Any] | None,
    config: dict[str, Any] | None,
    version: str | None,
    stage: bool | None,
    comment: str | None,
    secrets: dict[str, str] | None,
    overwrite: bool | None,
) -> dict[str, object]:
    """Typed builder for create() arguments (no artifact_id injection)."""
    return {
        k: v
        for k, v in {
            "alias": alias,
            "workspace": workspace,
            "parent_id": parent_id,
            "type": artifact_type,
            "manifest": manifest,
            "config": config,
            "version": version,
            "stage": stage,
            "comment": comment,
            "secrets": secrets,
            "overwrite": overwrite,
        }.items()
        if v is not None
    }


def params_put_file_start_multipart(
    file_path: str,
    *,
    part_count: int,
    download_weight: float = 1.0,
    use_proxy: bool | None = None,
    use_local_url: bool | str | None = None,
) -> dict[str, object]:
    p: dict[str, object] = {
        "file_path": file_path,
        "part_count": part_count,
        "download_weight": download_weight,
    }
    if use_proxy is not None:
        p["use_proxy"] = use_proxy
    if use_local_url is not None:
        p["use_local_url"] = use_local_url
    return p


def params_put_file_complete_multipart(
    upload_id: str,
    *,
    parts: list[dict[str, Any]],
) -> dict[str, object]:
    return {"upload_id": upload_id, "parts": parts}


def params_edit(
    *,
    manifest: dict[str, Any] | None = None,
    type: str | None = None,  # noqa: A002
    config: dict[str, Any] | None = None,
    secrets: dict[str, str] | None = None,
    version: str | None = None,
    comment: str | None = None,
    stage: bool = False,
) -> dict[str, object]:
    return {
        k: v
        for k, v in {
            "manifest": manifest,
            "type": type,
            "config": config,
            "secrets": secrets,
            "version": version,
            "comment": comment,
            "stage": stage,
        }.items()
        if v is not None
    }


def params_commit(
    *,
    version: str | None = None,
    comment: str | None = None,
) -> dict[str, object]:
    return {
        k: v
        for k, v in {"version": version, "comment": comment}.items()
        if v is not None
    }


def params_delete(
    *,
    delete_files: bool | None = None,
    recursive: bool | None = None,
    version: str | None = None,
) -> dict[str, object]:
    return {
        k: v
        for k, v in {
            "delete_files": delete_files,
            "recursive": recursive,
            "version": version,
        }.items()
        if v is not None
    }


def target_path_with_optional_slash(src_path: str, dst_path: str) -> str:
    """If dst ends with '/', append basename of src; otherwise return dst.

    Used by both get (remote->local) and put (local->remote) for intuitive semantics.
    """
    return (
        str(Path(dst_path) / Path(src_path).name)
        if dst_path.endswith("/")
        else dst_path
    )


def env_override(
    env_var_name: str,
    *,
    override: bool | str | None = None,
) -> bool | str | None:
    env_var_val = os.getenv(env_var_name)

    if override is not None:
        return override

    if env_var_val is not None:
        if env_var_val.lower() == "true":
            return True
        return env_var_val

    return None


def to_bytes(content: str | bytes | bytearray | memoryview) -> bytes:
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    return bytes(content)


def decode_to_text(content: str | bytes | bytearray | memoryview) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return bytes(content).decode("utf-8")


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
    async with self.open(remote_path, "rb", version=version) as fsrc:
        data = await fsrc.read()
    with Path(local_path).open("wb") as fdst:
        fdst.write(to_bytes(data))


async def upload_file_simple(
    self: AsyncHyphaArtifact,
    local_path: str | Path,
    remote_path: str,
) -> None:
    with Path(local_path).open("rb") as fsrc:
        data = fsrc.read()
    async with self.open(remote_path, "wb") as fdst:
        await fdst.write(data)


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


async def get_existing_url(urlpath: str) -> str:
    return urlpath


async def get_read_url(artifact: AsyncHyphaArtifact, params: dict[str, Any]) -> str:
    response = await artifact.get_client().get(
        get_method_url(artifact, ArtifactMethod.GET_FILE),
        params=params,
        headers=get_headers(artifact),
        timeout=60,
    )

    check_errors(response)

    return response.content.decode().strip('"')


async def get_write_url(artifact: AsyncHyphaArtifact, params: dict[str, Any]) -> str:
    response = await artifact.get_client().post(
        get_method_url(artifact, ArtifactMethod.PUT_FILE),
        json=params,
        headers=get_headers(artifact),
        timeout=60,
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
) -> dict[str, Any]:
    """Upload a single part."""
    part_number = part_info["part_number"]
    upload_url = part_info["url"]

    async with self.open(upload_url, "wb") as f:
        await f.write(part_info["chunk"])

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
    part_info: dict[str, Any],
) -> dict[str, Any]:
    async with semaphore:
        return await upload_part(self, part_info)


def should_use_multipart(file_size: int, multipart_config: dict[str, Any]) -> bool:
    """Determine if multipart upload should be used."""
    if not file_size > multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE):
        return False

    if multipart_config.get("enable"):
        return True

    return file_size >= multipart_config.get("threshold", DEFAULT_MULTIPART_THRESHOLD)


def handle_input_errors(
    file_size: int,
    chunk_size: int,
    multipart_config: dict[str, Any],
) -> None:
    """Handle input errors for multipart upload.

    Args:
        file_size (int): The size of the local file in bytes.
        chunk_size (int): The chunk size for the upload.
        multipart_config (dict[str, Any]): The multipart configuration.

    Raises:
        ValueError: If the input parameters are invalid.

    """
    if not should_use_multipart(file_size, multipart_config):
        return

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
    multipart_config: dict[str, Any],
    download_weight: float = 1.0,
) -> dict[str, Any]:
    """Start a multipart upload for a file."""
    chunk_size = multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE)
    file_size = local_path.stat().st_size
    handle_input_errors(file_size, chunk_size, multipart_config)
    part_count = math.ceil(file_size / chunk_size)

    start_params = params_put_file_start_multipart(
        file_path=remote_path,
        part_count=part_count,
        download_weight=download_weight,
        use_proxy=self.use_proxy,
        use_local_url=self.use_local_url,
    )
    start_params = prepare_params(self, start_params)

    start_url = get_method_url(self, ArtifactMethod.PUT_FILE_START_MULTIPART)
    start_resp = await self.get_client().post(
        start_url,
        headers=get_headers(self),
        json=start_params,
    )
    check_errors(start_resp)
    return start_resp.json()


async def upload_parts(
    self: AsyncHyphaArtifact,
    local_path: Path,
    chunk_size: int,
    parts: list[dict[str, Any]],
    max_parallel_uploads: int,
) -> list[dict[str, Any]]:
    """Upload parts of a file in parallel.

    Args:
        self (AsyncHyphaArtifact): The artifact instance.
        local_path (Path): The local file path.
        chunk_size (int): The size of each chunk.
        parts (list[dict[str, Any]]): The list of parts to upload.
        max_parallel_uploads (int): The maximum number of parallel uploads.

    Returns:
        list[dict[str, Any]]: The list of responses from the uploaded parts.

    """
    chunks = read_chunks(local_path, chunk_size)
    enumerate_parts = enumerate(zip(parts, chunks, strict=False))
    parts_info = [
        {
            "chunk": chunk,
            "url": part_info["url"],
            "part_number": part_info.get("part_number", index + 1),
        }
        for index, (part_info, chunk) in enumerate_parts
    ]

    semaphore = asyncio.Semaphore(max_parallel_uploads)
    upload_tasks = [
        upload_with_semaphore(self, semaphore, part_info) for part_info in parts_info
    ]

    return await asyncio.gather(*upload_tasks)


async def complete_multipart_upload(
    self: AsyncHyphaArtifact,
    upload_id: str,
    completed_parts: list[dict[str, Any]],
) -> None:
    """Complete a multipart upload.

    Args:
        self (AsyncHyphaArtifact): The artifact instance.
        upload_id (str): The ID of the upload.
        completed_parts (list[dict[str, Any]]): The list of completed parts.

    """
    simple_params = params_put_file_complete_multipart(
        upload_id=upload_id,
        parts=completed_parts,
    )
    complete_params = prepare_params(self, simple_params)
    complete_url = get_method_url(self, ArtifactMethod.PUT_FILE_COMPLETE_MULTIPART)
    complete_resp = await self.get_client().post(
        complete_url,
        json=complete_params,
        headers=get_headers(self),
    )
    check_errors(complete_resp)


async def upload_multipart(
    self: AsyncHyphaArtifact,
    local_path: Path,
    remote_path: str,
    multipart_config: dict[str, Any],
    download_weight: float = 1.0,
) -> None:
    """Upload a file using multipart upload with parallel uploads."""
    multipart_info = await start_multipart_upload(
        self,
        local_path,
        remote_path,
        multipart_config,
        download_weight=download_weight,
    )

    max_parallel_uploads = multipart_config.get("max_parallel_uploads", 4)
    parts = multipart_info["parts"]
    chunk_size = multipart_config.get("chunk_size", DEFAULT_CHUNK_SIZE)
    completed_parts = await upload_parts(
        self,
        local_path,
        chunk_size,
        parts,
        max_parallel_uploads,
    )

    upload_id = multipart_info["upload_id"]
    await complete_multipart_upload(self, upload_id, completed_parts)


def prepare_params(
    self: AsyncHyphaArtifact,
    params: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Extend parameters with artifact_id."""
    cleaned_params: dict[str, object] = {
        k: v for k, v in (dict(params or {})).items() if v is not None
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
        raise httpx.RequestError(error_msg)

    response.raise_for_status()
