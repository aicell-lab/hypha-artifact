"""Methods for filesystem-like operations."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

import httpx

from ._remote_methods import ArtifactMethod
from ._utils import (
    check_errors,
    filter_by_name,
    get_headers,
    get_method_url,
    params_list_files,
    params_remove_file,
    prepare_params,
    walk_dir,
)

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact
if TYPE_CHECKING:
    from hypha_artifact.classes import ArtifactItem


@overload
async def ls(
    self: AsyncHyphaArtifact,
    path: str = ".",
    version: str | None = None,
    *,
    detail: Literal[False],
) -> list[str]: ...


@overload
async def ls(
    self: AsyncHyphaArtifact,
    path: str = ".",
    version: str | None = None,
    *,
    detail: Literal[True],
) -> list[ArtifactItem]: ...


@overload
async def ls(
    self: AsyncHyphaArtifact,
    path: str = ".",
    version: str | None = None,
    *,
    detail: None | bool = True,
) -> list[ArtifactItem]: ...


async def ls(
    self: AsyncHyphaArtifact,
    path: str = ".",
    version: str | None = None,
    *,
    detail: None | bool = False,
) -> list[str] | list[ArtifactItem]:
    """List contents of path.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
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
    simple_params = params_list_files(dir_path=path, version=version)
    params = prepare_params(self, simple_params)

    url = get_method_url(self, ArtifactMethod.LIST_FILES)

    response = await self.get_client().get(
        url,
        params=params,
        headers=get_headers(self),
        timeout=60,
    )

    check_errors(response)

    artifact_items: list[ArtifactItem] = json.loads(response.content)

    if detail:
        return artifact_items

    return [item["name"] for item in artifact_items]


async def info(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> ArtifactItem:
    """Get information about a file or directory.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
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
    files_here = await self.ls(parent_path, detail=True, version=version)
    matching_files_here = filter_by_name(files_here, path)

    if matching_files_here:
        return matching_files_here[0]

    files_in_sub = await self.ls(path, detail=True, version=version)
    matching_files_in_sub = filter_by_name(files_in_sub, path)

    if len(matching_files_in_sub) == 1:
        return matching_files_in_sub[0]

    if len(matching_files_in_sub) > 1 or files_in_sub:
        return {"name": path, "type": "directory", "size": 0, "last_modified": None}

    raise FileNotFoundError(path)


async def isdir(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> bool:
    """Check if a path is a directory.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
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
    except (OSError, FileNotFoundError):
        return False


async def isfile(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> bool:
    """Check if a path is a file.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
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
    except (OSError, FileNotFoundError):
        return False


async def listdir(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> list[str]:
    """List files in a directory.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
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
    self: AsyncHyphaArtifact,
    path: str,
    maxdepth: int | None = None,
    version: str | None = None,
    *,
    withdirs: bool = False,
    detail: Literal[True],
    hide_keep: bool = True,
) -> dict[str, ArtifactItem]: ...


@overload
async def find(
    self: AsyncHyphaArtifact,
    path: str,
    maxdepth: int | None = None,
    version: str | None = None,
    *,
    withdirs: bool = False,
    detail: Literal[False] = False,
    hide_keep: bool = True,
) -> list[str]: ...


async def find(
    self: AsyncHyphaArtifact,
    path: str,
    maxdepth: int | None = None,
    version: str | None = None,
    *,
    withdirs: bool = False,
    detail: bool = False,
    hide_keep: bool = True,
) -> list[str] | dict[str, ArtifactItem]:
    """Find all files (and optional directories) under a path.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
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
    hide_keep: bool
        If True, exclude .keep files from the results.
        If False, include .keep files in the results.

    Returns
    -------
    list or dict
        List of paths or dict of {path: info_dict}

    """
    filtered_all_files = await walk_dir(
        self,
        path,
        maxdepth,
        1,
        version,
        withdirs=withdirs,
    )

    filtered_all_files = (
        {k: v for k, v in filtered_all_files.items() if not k.endswith(".keep")}
        if hide_keep
        else filtered_all_files
    )

    if detail:
        return filtered_all_files

    return sorted(filtered_all_files.keys())


async def modified(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> datetime.datetime | None:
    """Return the modified timestamp of a file as a datetime.datetime.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to the file
    version: str | None = None
        The version of the artifact to check against.
        By default, it checks the latest version.
        If you want to check a staged version, you can set it to "stage".

    Returns
    -------
    datetime or None
        Modified time of the file, if available

    """
    path_info = await self.info(path, version=version)

    last_modified = path_info["last_modified"]

    if last_modified:
        return datetime.datetime.fromtimestamp(
            last_modified,
            tz=datetime.UTC,
        )

    return None


async def size(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> int:
    """Get the size of a file in bytes.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
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
    self: AsyncHyphaArtifact,
    paths: list[str],
    version: str | None = None,
) -> list[int]:
    """Get the size of multiple files.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
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
    return [await self.size(path, version=version) for path in paths]


async def rm(
    self: AsyncHyphaArtifact,
    path: str,
    maxdepth: int | None = None,
    *,
    recursive: bool = False,
) -> None:
    """Remove file or directory.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to the file or directory to remove
    recursive: bool
        Defaults to False. If True and path is a directory,
        remove all its contents recursively
    maxdepth: int or None
        Maximum recursion depth when recursive=True

    Returns
    -------
    datetime or None
        Creation time of the file, if available

    """
    paths_to_remove: list[str] = []
    is_dir = await self.isdir(path)
    if recursive and is_dir:
        paths_to_remove = await self.find(
            path,
            maxdepth=maxdepth,
            withdirs=False,
            detail=False,
            hide_keep=False,
        )
    elif not recursive and is_dir:
        error_msg = (
            f"Path is a directory: {path}. Use --recursive to remove directories."
        )
        raise IsADirectoryError(error_msg)
    else:
        paths_to_remove.append(path)

    for file_path in paths_to_remove:
        simple_params = params_remove_file(file_path)
        params = prepare_params(self, simple_params)
        response = await self.get_client().post(
            url=get_method_url(self, ArtifactMethod.REMOVE_FILE),
            headers=get_headers(self),
            json=params,
        )

        check_errors(response)


async def rm_file(self: AsyncHyphaArtifact, path: str) -> None:
    """Remove a file.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to remove

    """
    await self.rm(path)


async def rmdir(self: AsyncHyphaArtifact, path: str) -> None:
    """Remove an empty directory.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to remove

    """
    if not await self.isdir(path):
        error_msg = f"Directory not found: {path}"
        raise FileNotFoundError(error_msg)

    file_names = await self.ls(path, detail=False)
    has_keep = any(f_name == ".keep" for f_name in file_names)
    if (not has_keep and len(file_names) > 0) or (has_keep and len(file_names) > 1):
        error_msg = f"Directory not empty: {path}"
        raise OSError(error_msg)

    await self.rm(str(Path(path) / ".keep"))


async def touch(
    self: AsyncHyphaArtifact,
    path: str,
    *,
    truncate: bool = True,
) -> None:
    """Create a file if it does not exist, or update its last modified time.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to the file
    truncate: bool
        If True, always set file size to 0;
        if False, update timestamp and leave file unchanged

    """
    async with self.open(path, "wb") as f:
        if truncate or not await self.exists(path):
            return

        if not truncate:
            current_content = await f.read()
            f.seek(0)
            await f.write(current_content)


async def mkdir(
    self: AsyncHyphaArtifact,
    path: str,
    *,
    create_parents: bool = True,
) -> None:
    """Create a directory.

    Creates a .keep file in the directory to ensure it exists.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The AsyncHyphaArtifact instance to use
    path: str
        Path to create
    create_parents: bool
        If True, create parent directories if they don't exist

    """
    if Path(path) == Path():
        return

    parent_path = str(Path(path).parent)
    child_path = str(Path(path).name)

    if parent_path and not await self.exists(parent_path):
        if not create_parents:
            error_msg = f"Parent directory does not exist: {parent_path}"
            raise FileNotFoundError(error_msg)

        await self.mkdir(parent_path, create_parents=True)

    if parent_path and await self.isfile(parent_path):
        error_msg = f"Parent path is not a directory: {parent_path}"
        raise NotADirectoryError(error_msg)

    await self.touch(str(Path(child_path) / ".keep"))


async def makedirs(
    self: AsyncHyphaArtifact,
    path: str,
    *,
    exist_ok: bool = True,
) -> None:
    """Recursively make directories.

    Creates directory at path and any intervening required directories.
    Raises exception if, for instance, the path already exists but is a
    file.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
    path: str
        Path to create
    exist_ok: bool
        If False and the directory exists, raise an error

    """
    if not exist_ok and await self.exists(path):
        error_msg = f"Directory already exists: {path}"
        raise FileExistsError(error_msg)

    await self.mkdir(path, create_parents=True)


async def exists(
    self: AsyncHyphaArtifact,
    path: str,
    version: str | None = None,
) -> bool:
    """Check if a file or directory exists.

    Parameters
    ----------
    self: AsyncHyphaArtifact
        The HyphaArtifact instance to use
    path: str
        Path to check
    version: str | None
        The version of the artifact to check against. If None, uses the latest version.

    Returns
    -------
    bool
        True if the path exists, False otherwise

    """
    try:
        async with self.open(path, "r", version=version) as f:
            await f.read(0)
            return True
    except (OSError, FileNotFoundError, httpx.HTTPStatusError, httpx.RequestError):
        try:
            dir_files = await self.ls(path, detail=False, version=version)
            return len(dir_files) > 0
        except (OSError, FileNotFoundError, httpx.HTTPStatusError, httpx.RequestError):
            return False
