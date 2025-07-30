# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Methods for file I/O operations."""

from __future__ import annotations

import os
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    overload,
)

import httpx

from ..utils import FileMode, OnError, normalize_path
from ..async_artifact_file import AsyncArtifactHttpFile

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
    """Get file(s) content as string(s)"""
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
    self: "AsyncHyphaArtifact",  # pylint: disable=unused-argument
    urlpath: str,
    mode: FileMode = "rb",
    **kwargs: Any,
) -> AsyncArtifactHttpFile:
    """Open a file for reading or writing"""
    normalized_path = normalize_path(urlpath)

    if "r" in mode:

        async def get_url():
            return await self._remote_get_file_url(normalized_path)

    elif "w" in mode or "a" in mode:

        async def get_url():
            url = await self._remote_put_file_url(normalized_path)
            return url

    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return AsyncArtifactHttpFile(
        get_url,
        mode=mode,
        name=normalized_path,
    )


async def copy(
    self: "AsyncHyphaArtifact",  # pylint: disable=unused-argument
    path1: str,
    path2: str,
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError | None = "raise",
    **kwargs: dict[str, Any],
) -> None:
    """Copy file(s) from path1 to path2 within the artifact"""
    if recursive and await self.isdir(path1):
        files = await self.find(path1, maxdepth=maxdepth, withdirs=False)
        for src_path in files:
            rel_path = src_path[len(path1) :].lstrip("/")
            dst_path = f"{path2}/{rel_path}"
            try:
                await self._copy_single_file(src_path, dst_path)
            except (FileNotFoundError, IOError, httpx.RequestError) as e:
                if on_error == "raise":
                    raise e
    else:
        await self._copy_single_file(path1, path2)


def _callback_msg(
    file_dict: str,
    num_total_files: int,
    current_file_index: int,
) -> dict[str, dict[str, Any] | str | int]:
    """Create a progress callback message."""
    return {
        "type": "info",
        "message": f"Downloading file {current_file_index + 1}/{num_total_files}: {file_dict}",
        "file": file_dict,
        "total_files": num_total_files,
        "current_file": current_file_index + 1,
    }


async def get_list(
    self: "AsyncHyphaArtifact",
    rpath: list[str],
    lpath: list[str],
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    progress_callback: None | Callable[[dict[str, Any]], None] = None,
    **kwargs: dict[str, Any],
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem"""
    if len(rpath) != len(lpath):
        raise ValueError("rpath and lpath must be lists of the same length")

    if progress_callback:
        progress_callback(
            {
                "type": "info",
                "message": f"Starting download of {len(rpath)} files",
                "total_files": len(rpath),
                "current_file": 0,
            }
        )

    for i, (rp, lp) in enumerate(zip(rpath, lpath)):
        if progress_callback:
            callback_msg = _callback_msg(
                rp,
                len(rpath),
                i,
            )
            progress_callback(callback_msg)

        await self.get(
            rp,
            lp,
            recursive=recursive,
            maxdepth=maxdepth,
            on_error=on_error,
            progress_callback=progress_callback,
            **kwargs,
        )


async def get_recursive(
    self: "AsyncHyphaArtifact",  # pylint: disable=unused-argument
    rpath: str,
    lpath: str,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    progress_callback: None | Callable[[dict[str, Any]], None] = None,
    **kwargs: Any,
) -> None:
    """Helper method to recursively copy files from remote to local"""
    os.makedirs(lpath, exist_ok=True)

    if progress_callback:
        progress_callback(
            {
                "type": "info",
                "message": f"Starting recursive download from {rpath}",
                "file": rpath,
            }
        )

    files = await self.find(rpath, maxdepth=maxdepth, withdirs=False)

    if progress_callback:
        progress_callback(
            {
                "type": "info",
                "message": f"Found {len(files)} files to download",
                "total_files": len(files),
                "current_file": 0,
            }
        )

    for i, remote_file in enumerate(files):
        if rpath:
            rel_path = remote_file[len(rpath) :].lstrip("/")
        else:
            rel_path = remote_file
        local_file = os.path.join(lpath, rel_path)

        local_dir = os.path.dirname(local_file)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)

        if progress_callback:
            callback_msg = _callback_msg(
                remote_file,
                len(files),
                i,
            )
            progress_callback(callback_msg)

        try:
            await self._get_single_file(remote_file, local_file)
            if progress_callback:
                progress_callback(
                    {
                        "type": "success",
                        "message": f"Successfully downloaded: {remote_file}",
                        "file": remote_file,
                    }
                )
        except (FileNotFoundError, IOError, httpx.RequestError) as e:
            if progress_callback:
                progress_callback(
                    {
                        "type": "error",
                        "message": f"Failed to download {remote_file}: {str(e)}",
                        "file": remote_file,
                    }
                )
            if on_error == "raise":
                raise e


async def get_single_file(
    self: "AsyncHyphaArtifact", remote_path: str, local_path: str
) -> None:
    """Helper method to copy a single file from remote to local"""
    async with self.open(remote_path, "rb") as remote_file:
        content = await remote_file.read()

    content_bytes = content.encode("utf-8") if isinstance(content, str) else content

    with open(local_path, "wb") as local_file:
        local_file.write(content_bytes)


async def get(
    self: "AsyncHyphaArtifact",
    rpath: str | list[str],
    lpath: str | list[str],
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    progress_callback: None | Callable[[dict[str, Any]], None] = None,
    **kwargs: Any,
) -> None:
    """Copy file(s) from remote (artifact) to local filesystem"""
    if isinstance(rpath, list) and isinstance(lpath, list):
        await self._get_list(
            rpath,
            lpath,
            recursive=recursive,
            maxdepth=maxdepth,
            on_error=on_error,
            progress_callback=progress_callback,
            **kwargs,
        )
        return

    assert isinstance(rpath, str) and isinstance(
        lpath, str
    ), "rpath and lpath must be either both strings or both lists of strings"

    if recursive and await self.isdir(rpath):
        await self._get_recursive(
            rpath,
            lpath,
            maxdepth=maxdepth,
            on_error=on_error,
            progress_callback=progress_callback,
            **kwargs,
        )
        return

    local_dir = os.path.dirname(lpath)
    os.makedirs(local_dir, exist_ok=True)

    if progress_callback:
        progress_callback(
            {
                "type": "info",
                "message": f"Downloading single file: {rpath}",
                "file": rpath,
            }
        )

    try:
        await self._get_single_file(rpath, lpath)
        if progress_callback:
            progress_callback(
                {
                    "type": "success",
                    "message": f"Successfully downloaded: {rpath}",
                    "file": rpath,
                }
            )
    except (FileNotFoundError, IOError, httpx.RequestError) as e:
        if progress_callback:
            progress_callback(
                {
                    "type": "error",
                    "message": f"Failed to download {rpath}: {str(e)}",
                    "file": rpath,
                }
            )
        raise e


async def put_list(
    self: "AsyncHyphaArtifact",
    lpaths: list[str],
    rpaths: list[str],
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    progress_callback: None | Callable[[dict[str, Any]], None] = None,
    **kwargs: dict[str, Any],
) -> None:
    """Helper method to copy a list of files from local to remote"""
    if len(lpaths) != len(rpaths):
        raise ValueError("lpath and rpath must be lists of the same length")

    if progress_callback:
        progress_callback(
            {
                "type": "info",
                "message": f"Starting upload of {len(lpaths)} files",
                "total_files": len(lpaths),
                "current_file": 0,
            }
        )

    for i, (lpath, rpath) in enumerate(zip(lpaths, rpaths)):
        if progress_callback:
            progress_callback(
                {
                    "type": "info",
                    "message": f"Uploading file {i+1}/{len(lpaths)}",
                    "file": lpath,
                    "total_files": len(lpaths),
                    "current_file": i + 1,
                }
            )

        await self.put(
            lpath,
            rpath,
            recursive,
            maxdepth,
            on_error,
            progress_callback=progress_callback,
            **kwargs,
        )
    return


async def put(
    self: "AsyncHyphaArtifact",
    lpath: str | list[str],
    rpath: str | list[str],
    recursive: bool = False,
    maxdepth: int | None = None,
    on_error: OnError = "raise",
    progress_callback: None | Callable[[dict[str, Any]], None] = None,
    **kwargs: Any,
) -> None:
    """Copy file(s) from local filesystem to remote (artifact)"""
    if isinstance(lpath, list) and isinstance(rpath, list):
        await self._put_list(
            lpath, rpath, recursive, maxdepth, on_error, progress_callback, **kwargs
        )

    assert isinstance(lpath, str) and isinstance(
        rpath, str
    ), "lpath and rpath must be either both strings or both lists of strings"

    if recursive and os.path.isdir(lpath):
        await self.makedirs(rpath, exist_ok=True)

        if progress_callback:
            progress_callback(
                {
                    "type": "info",
                    "message": f"Starting recursive upload from {lpath}",
                    "file": lpath,
                }
            )

        all_files: list[str] = []
        for root, dirs, files in os.walk(lpath):
            for file_name in files:
                local_file = os.path.join(root, file_name)
                all_files.append(local_file)

        if progress_callback:
            progress_callback(
                {
                    "type": "info",
                    "message": f"Found {len(all_files)} files to upload",
                    "total_files": len(all_files),
                    "current_file": 0,
                }
            )

        for root, dirs, files in os.walk(lpath):
            rel_root = os.path.relpath(root, lpath)
            if rel_root == ".":
                remote_dir = rpath
            else:
                remote_dir = f"{rpath}/{rel_root}"

            for dir_name in dirs:
                remote_subdir = f"{remote_dir}/{dir_name}"
                await self.makedirs(remote_subdir, exist_ok=True)

            for file_name in files:
                local_file = os.path.join(root, file_name)
                remote_file = f"{remote_dir}/{file_name}"

                current_index = all_files.index(local_file) + 1

                if progress_callback:
                    progress_callback(
                        {
                            "type": "info",
                            "message": f"Uploading file {current_index}/{len(all_files)}: {local_file}",
                            "file": local_file,
                            "total_files": len(all_files),
                            "current_file": current_index,
                        }
                    )

                try:
                    await self._put_single_file(local_file, remote_file)
                    if progress_callback:
                        progress_callback(
                            {
                                "type": "success",
                                "message": f"Successfully uploaded: {local_file}",
                                "file": local_file,
                            }
                        )
                except (FileNotFoundError, IOError, httpx.RequestError) as e:
                    if progress_callback:
                        progress_callback(
                            {
                                "type": "error",
                                "message": f"Failed to upload {local_file}: {str(e)}",
                                "file": local_file,
                            }
                        )
                    if on_error == "raise":
                        raise e
    else:
        if progress_callback:
            progress_callback(
                {
                    "type": "info",
                    "message": f"Uploading single file: {lpath}",
                    "file": lpath,
                }
            )

        try:
            await self._put_single_file(lpath, rpath)
            if progress_callback:
                progress_callback(
                    {
                        "type": "success",
                        "message": f"Successfully uploaded: {lpath}",
                        "file": lpath,
                    }
                )
        except (FileNotFoundError, IOError, httpx.RequestError) as e:
            if progress_callback:
                progress_callback(
                    {
                        "type": "error",
                        "message": f"Failed to upload {lpath}: {str(e)}",
                        "file": lpath,
                    }
                )
            raise e


async def put_single_file(
    self: "AsyncHyphaArtifact", local_path: str, remote_path: str
) -> None:
    """Helper method to copy a single file from local to remote"""
    with open(local_path, "rb") as local_file:
        content = local_file.read()

    async with self.open(remote_path, "wb") as remote_file:
        await remote_file.write(content)


async def copy_single_file(self: "AsyncHyphaArtifact", src: str, dst: str) -> None:
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
    """Alias for copy method"""
    recursive = kwargs.pop("recursive", False)
    maxdepth = kwargs.pop("maxdepth", None)
    return await self.copy(
        path1, path2, recursive=recursive, maxdepth=maxdepth, on_error=on_error
    )


async def head(self: "AsyncHyphaArtifact", path: str, size: int = 1024) -> bytes:
    """Get the first bytes of a file"""
    async with self.open(path, "rb") as f:
        result = await f.read(size)
        if isinstance(result, bytes):
            return result
        elif isinstance(result, str):
            return result.encode()
        else:
            return bytes(result)
