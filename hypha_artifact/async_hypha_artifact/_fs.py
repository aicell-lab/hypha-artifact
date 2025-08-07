"""Methods for filesystem-like operations."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    overload,
)

from datetime import datetime
from pathlib import Path

import httpx

from ..classes import ArtifactItem

from ._remote import (
    remote_list_contents,
    remote_remove_file,
)
from ._utils import walk_dir

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[False],
    **kwargs: Any,
) -> list[str]: ...


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[True],
    **kwargs: Any,
) -> list[ArtifactItem]: ...


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> list[ArtifactItem]: ...


# TODO: test with directories
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[True] | Literal[False] = True,
    **kwargs: Any,
) -> list[str] | list[ArtifactItem]:
    """List contents of path"""
    contents = await remote_list_contents(self, path)

    if detail:
        return [ArtifactItem(**item) for item in contents if isinstance(item, dict)]

    return [item["name"] for item in contents if isinstance(item, dict)]


async def info(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> ArtifactItem:
    """Get information about a file or directory

    Parameters
    ----------
    path: str
        Path to get information about

    Returns
    -------
    dict
        Dictionary with file information
    """
    parent_path = str(Path(path).parent)

    out = await self.ls(parent_path, detail=True, **kwargs)
    out = [o for o in out if str(o["name"]).rstrip("/") == Path(path).name]

    if out:
        return out[0]

    out = await self.ls(path, detail=True, **kwargs)
    path = str(Path(path))
    out1 = [o for o in out if str(o["name"]).rstrip("/") == path]
    if len(out1) == 1:
        return out1[0]
    elif len(out1) > 1 or out:
        return {"name": path, "type": "directory", "size": 0, "last_modified": None}
    else:
        raise FileNotFoundError(path)


async def isdir(self: "AsyncHyphaArtifact", path: str) -> bool:
    """Check if a path is a directory

    Parameters
    ----------
    path: str
        Path to check

    Returns
    -------
    bool
        True if the path is a directory, False otherwise
    """
    try:
        path_info = await self.info(path)
        return path_info["type"] == "directory"
    except (FileNotFoundError, IOError):
        return False


async def isfile(self: "AsyncHyphaArtifact", path: str) -> bool:
    """Check if a path is a file

    Parameters
    ----------
    path: str
        Path to check

    Returns
    -------
    bool
        True if the path is a file, False otherwise
    """
    try:
        path_info = await self.info(path)
        return path_info["type"] == "file"
    except (FileNotFoundError, IOError):
        return False


async def listdir(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> list[str]:
    """List files in a directory

    Parameters
    ----------
    path: str
        Path to list
    **kwargs: dict[str, Any]
        Additional arguments passed to the ls method

    Returns
    -------
    list of str
        List of file names in the directory
    """
    return await self.ls(path, detail=False)


@overload
async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    *,
    detail: Literal[True],
    **kwargs: dict[str, Any],
) -> dict[str, ArtifactItem]: ...


@overload
async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    detail: Literal[False] = False,
    **kwargs: dict[str, Any],
) -> list[str]: ...


async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    detail: bool = False,
    **kwargs: dict[str, Any],
) -> list[str] | dict[str, ArtifactItem]:
    """Find all files (and optional directories) under a path

    Parameters
    ----------
    path: str
        Base path to search from
    maxdepth: int or None
        Maximum recursion depth when searching
    withdirs: bool
        Whether to include directories in the results
    detail: bool
        If True, return a dict of {path: info_dict}
        If False, return a list of paths

    Returns
    -------
    list or dict
        List of paths or dict of {path: info_dict}
    """

    all_files = await walk_dir(self, path, maxdepth, withdirs, 1)

    if detail:
        return all_files

    return sorted(all_files.keys())


# TODO: currently returns last modified time, not creation time
async def created(self: "AsyncHyphaArtifact", path: str) -> datetime | None:
    """Get the creation time of a file

    In the Hypha artifact system, we might not have direct access to creation time,
    but we can retrieve this information from file metadata if available.

    Parameters
    ----------
    path: str
        Path to the file

    Returns
    -------
    datetime or None
        Creation time of the file, if available
    """
    path_info = await self.info(path)

    last_modified = path_info["last_modified"]

    if last_modified:
        datetime_modified = datetime.fromtimestamp(last_modified)
        return datetime_modified

    return None


async def size(self: "AsyncHyphaArtifact", path: str) -> int:
    """Get the size of a file in bytes

    Parameters
    ----------
    path: str
        Path to the file

    Returns
    -------
    int
        Size of the file in bytes
    """
    path_info = await self.info(path)
    if path_info["type"] == "directory":
        return 0
    return int(path_info["size"])


async def sizes(self: "AsyncHyphaArtifact", paths: list[str]) -> list[int]:
    """Get the size of multiple files

    Parameters
    ----------
    paths: list of str
        List of paths to get sizes for

    Returns
    -------
    list of int
        List of file sizes in bytes
    """
    return [await self.size(path) for path in paths]


async def rm(
    self: "AsyncHyphaArtifact",
    path: str,
    recursive: bool = False,
    maxdepth: int | None = None,
) -> None:
    """Remove file or directory

    Parameters
    ----------

    path: str
        Path to the file or directory to remove
    recursive: bool
        Defaults to False. If True and path is a directory, remove all its contents recursively
    maxdepth: int or None
        Maximum recursion depth when recursive=True

    Returns
    -------
    datetime or None
        Creation time of the file, if available
    """
    if recursive and await self.isdir(path):
        files = await self.find(path, maxdepth=maxdepth, withdirs=False, detail=False)
        for file_path in files:
            await remote_remove_file(self, file_path)
    else:
        await remote_remove_file(self, path)


async def delete(
    self: "AsyncHyphaArtifact",
    path: str,
    recursive: bool = False,
    maxdepth: int | None = None,
) -> None:
    """Delete a file or directory from the artifact

    Args:
        self (Self): The instance of the class.
        path (str): The path to the file or directory to delete.
        recursive (bool, optional): Whether to delete directories recursively.
            Defaults to False.
        maxdepth (int | None, optional): The maximum depth to delete. Defaults to None.

    Returns:
        None
    """
    return await self.rm(path, recursive=recursive, maxdepth=maxdepth)


async def rm_file(self: "AsyncHyphaArtifact", path: str) -> None:
    """Remove a file

    Parameters
    ----------
    path: str
        Path to remove
    """
    await self.rm(path)


async def rmdir(self: "AsyncHyphaArtifact", path: str) -> None:
    """Remove an empty directory

    In the Hypha artifact system, directories are implicit, so this would
    only make sense if the directory is empty. Since empty directories
    don't really exist explicitly, this is essentially a validation check
    that no files exist under this path.

    Parameters
    ----------
    path: str
        Path to remove
    """
    if not await self.isdir(path):
        raise FileNotFoundError(f"Directory not found: {path}")

    files = await self.ls(path)
    if files:
        raise OSError(f"Directory not empty: {path}")


async def touch(
    self: "AsyncHyphaArtifact",
    path: str,
    truncate: bool = True,
    **kwargs: Any,
) -> None:
    """Create a file if it does not exist, or update its last modified time

    Parameters
    ----------
    path: str
        Path to the file
    truncate: bool
        If True, always set file size to 0;
        if False, update timestamp and leave file unchanged
    """
    if truncate or not await self.exists(path):
        async with self.open(path, "wb", **kwargs):
            pass

    # TODO: handle not truncate option


async def mkdir(
    self: "AsyncHyphaArtifact",
    path: str,
    create_parents: bool = True,
    **kwargs: Any,
) -> None:
    """Create a directory

    Creates a .keep file in the directory to ensure it exists.

    Parameters
    ----------
    path: str
        Path to create
    create_parents: bool
        If True, create parent directories if they don't exist
    """
    if path in ["", "/"]:
        return

    parent_path = str(Path(path).parent)
    child_path = str(Path(path).name)

    if parent_path and not await self.exists(parent_path):
        if not create_parents:
            raise FileNotFoundError(f"Parent directory does not exist: {parent_path}")

        await self.mkdir(parent_path, create_parents=True)

    if parent_path and await self.isfile(parent_path):
        raise NotADirectoryError(f"Parent path is not a directory: {parent_path}")

    await self.touch(str(Path(child_path) / ".keep"))


async def makedirs(
    self: "AsyncHyphaArtifact",
    path: str,
    exist_ok: bool = True,
) -> None:
    """Recursively make directories

    Creates directory at path and any intervening required directories.
    Raises exception if, for instance, the path already exists but is a
    file.

    Parameters
    ----------
    path: str
        Path to create
    exist_ok: bool
        If False and the directory exists, raise an error
    """
    if not exist_ok and await self.exists(path):
        raise FileExistsError(f"Directory already exists: {path}")

    await self.mkdir(path, create_parents=True)


async def exists(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> bool:
    """Check if a file or directory exists

    Parameters
    ----------
    path: str
        Path to check

    Returns
    -------
    bool
        True if the path exists, False otherwise
    """
    try:
        async with self.open(path, "r") as f:
            await f.read(0)
            return True
    except (FileNotFoundError, IOError, httpx.RequestError):
        try:
            dir_files = await self.ls(path, detail=False, **kwargs)
            return len(dir_files) > 0
        except (FileNotFoundError, IOError, httpx.RequestError):
            return False
