"""Methods for filesystem-like operations."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    overload,
)

import json
from datetime import datetime
from pathlib import Path

import httpx

from ..classes import ArtifactItem

from ._remote_methods import ArtifactMethod
from ._utils import walk_dir, prepare_params, get_method_url, get_headers, check_errors

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[False],
    version: str | None = None,
) -> list[str]: ...


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[True],
    version: str | None = None,
) -> list[ArtifactItem]: ...


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: None | bool = True,
    version: str | None = None,
) -> list[ArtifactItem]: ...


# TODO: test with directories
# TODO: shorten
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: None | bool = True,
    version: str | None = None,
) -> list[str] | list[ArtifactItem]:
    """List contents of path

    Parameters
    ----------
    path: str
        Path to list contents of
    detail: bool | None
        Whether to include detailed information about each item
    version: str | None
        The version of the artifact to list contents from.
        By default, it lists from the latest version.
        If you want to list from a staged version, you can set it to "stage".

    Returns
    -------
    list[str] | list[ArtifactItem]
        List of file names or detailed artifact items
    """
    params: dict[str, Any] = prepare_params(
        self,
        {
            "dir_path": path,
            "version": version,
        },
    )

    url = get_method_url(self, ArtifactMethod.LIST_FILES)

    response = await self.get_client().get(
        url,
        params=params,
        headers=get_headers(self),
        timeout=20,
    )

    check_errors(response)

    artifact_items: list[ArtifactItem] = json.loads(response.content)

    if detail:
        return artifact_items

    return [item["name"] for item in artifact_items]


async def info(
    self: "AsyncHyphaArtifact",
    path: str,
    version: str | None = None,
) -> ArtifactItem:
    """Get information about a file or directory

    Parameters
    ----------
    path: str
        Path to get information about
    version:
        The version of the artifact to get the information from.
        By default, it reads from the latest version.
        If you want to read from a staged version, you can set it to "stage".

    Returns
    -------
    dict
        Dictionary with file information
    """
    parent_path = str(Path(path).parent)

    out = await self.ls(parent_path, detail=True, version=version)
    out = [o for o in out if str(o["name"]).rstrip("/") == Path(path).name]

    if out:
        return out[0]

    out = await self.ls(path, detail=True, version=version)
    path = str(Path(path))
    out1 = [o for o in out if str(o["name"]).rstrip("/") == path]
    if len(out1) == 1:
        return out1[0]
    elif len(out1) > 1 or out:
        return {"name": path, "type": "directory", "size": 0, "last_modified": None}
    else:
        raise FileNotFoundError(path)


async def isdir(
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
) -> bool:
    """Check if a path is a directory

    Parameters
    ----------
    path: str
        Path to check
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

    Returns
    -------
    bool
        True if the path is a directory, False otherwise
    """
    try:
        path_info = await self.info(path, version=version)
        return path_info["type"] == "directory"
    except (FileNotFoundError, IOError):
        return False


async def isfile(
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
) -> bool:
    """Check if a path is a file

    Parameters
    ----------
    path: str
        Path to check
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

    Returns
    -------
    bool
        True if the path is a file, False otherwise
    """
    try:
        path_info = await self.info(path, version=version)
        return path_info["type"] == "file"
    except (FileNotFoundError, IOError):
        return False


async def listdir(
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
) -> list[str]:
    """List files in a directory

    Parameters
    ----------
    path: str
        Path to list
    version: str | None = None
        The version of the artifact to get the information from.
        By default, it reads from the latest version.
        If you want to read from a staged version, you can set it to "stage".

    Returns
    -------
    list of str
        List of file names in the directory
    """
    return await self.ls(path, detail=False, version=version)


@overload
async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    version: str | None = None,
    *,
    detail: Literal[True],
) -> dict[str, ArtifactItem]: ...


@overload
async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    version: str | None = None,
    detail: Literal[False] = False,
) -> list[str]: ...


async def find(
    self: "AsyncHyphaArtifact",
    path: str,
    maxdepth: int | None = None,
    withdirs: bool = False,
    version: str | None = None,
    detail: bool = False,
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
    version: str | None
        The version of the artifact to search in.
        By default, it searches in the latest version.
        If you want to search in a staged version, you can set it to "stage".

    Returns
    -------
    list or dict
        List of paths or dict of {path: info_dict}
    """

    all_files = await walk_dir(self, path, maxdepth, withdirs, 1, version=version)

    if detail:
        return all_files

    return sorted(all_files.keys())


# TODO: currently returns last modified time, not creation time
async def created(
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
) -> datetime | None:
    """Get the creation time of a file

    In the Hypha artifact system, we might not have direct access to creation time,
    but we can retrieve this information from file metadata if available.

    Parameters
    ----------
    path: str
        Path to the file
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

    Returns
    -------
    datetime or None
        Creation time of the file, if available
    """
    path_info = await self.info(path, version=version)

    last_modified = path_info["last_modified"]

    if last_modified:
        datetime_modified = datetime.fromtimestamp(last_modified)
        return datetime_modified

    return None


async def size(
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
) -> int:
    """Get the size of a file in bytes

    Parameters
    ----------
    path: str
        Path to the file
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

    Returns
    -------
    int
        Size of the file in bytes
    """
    path_info = await self.info(path, version=version)
    if path_info["type"] == "directory":
        return 0
    return int(path_info["size"])


async def sizes(
    self: "AsyncHyphaArtifact", paths: list[str], version: str | None = None
) -> list[int]:
    """Get the size of multiple files

    Parameters
    ----------
    paths: list of str
        List of paths to get sizes for
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

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
    paths_to_remove: list[str] = []
    if recursive and await self.isdir(path):
        files = await self.find(path, maxdepth=maxdepth, withdirs=False, detail=False)
        for file_path in files:
            paths_to_remove.append(file_path)
    else:
        paths_to_remove.append(path)

    for file_path in paths_to_remove:
        params: dict[str, Any] = prepare_params(
            self,
            {
                "file_path": file_path,
            },
        )

        await self.get_client().post(
            url=get_method_url(self, ArtifactMethod.REMOVE_FILE),
            headers=get_headers(self),
            json=params,
        )


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


# TODO: fix
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
        async with self.open(path, "wb"):
            pass

    # TODO: handle not truncate option


async def mkdir(
    self: "AsyncHyphaArtifact",
    path: str,
    create_parents: bool = True,
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
    self: "AsyncHyphaArtifact", path: str, version: str | None = None
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
        async with self.open(path, "r", version=version) as f:
            await f.read(0)
            return True
    except (FileNotFoundError, IOError, httpx.HTTPStatusError, httpx.RequestError):
        try:
            dir_files = await self.ls(path, detail=False, version=version)
            return len(dir_files) > 0
        except (FileNotFoundError, IOError, httpx.HTTPStatusError, httpx.RequestError):
            return False
