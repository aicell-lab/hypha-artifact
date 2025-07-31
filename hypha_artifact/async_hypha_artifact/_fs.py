# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Methods for filesystem-like operations."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    overload,
)

import httpx

from ..utils import parent_and_filename, normalize_path

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
) -> list[dict[str, Any]]: ...


@overload
async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> list[dict[str, Any]]: ...


async def ls(
    self: "AsyncHyphaArtifact",
    path: str,
    detail: Literal[True] | Literal[False] = True,
    **kwargs: Any,
) -> list[str] | list[dict[str, Any]]:
    """List contents of path"""
    contents = await self._remote_list_contents(normalize_path(path))

    if detail:
        # TODO: check output
        return [item for item in contents if isinstance(item, dict)]

    return [item.get("name", "") for item in contents if isinstance(item, dict)]


async def info(
    self: "AsyncHyphaArtifact",
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
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
    normalized_path = normalize_path(path)
    parent_path, filename = parent_and_filename(normalized_path)

    if parent_path is None:
        parent_path = ""

    if normalized_path == "":
        return {"name": "", "type": "directory"}

    listing = await self.ls(parent_path)
    for item in listing:
        if item.get("name") == filename:
            return item

    raise FileNotFoundError(f"Path not found: {path}")


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
        return path_info.get("type") == "directory"
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
        return path_info.get("type") == "file"
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
) -> dict[str, dict[str, Any]]: ...


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
) -> list[str] | dict[str, dict[str, Any]]:
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

    async def _walk_dir(
        current_path: str, current_depth: int
    ) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}

        try:
            items = await self.ls(current_path)
        except (FileNotFoundError, IOError, httpx.RequestError):
            return {}

        for item in items:
            item_type = item.get("type")
            item_name = item.get("name")

            if (
                item_type == "file" or (withdirs and item_type == "directory")
            ) and isinstance(item_name, str):
                full_path = f"{current_path}/{item_name}" if current_path else item_name
                results[full_path] = item

            if (
                item_type == "directory"
                and (maxdepth is None or current_depth < maxdepth)
                and isinstance(item_name, str)
            ):
                subdir_path = (
                    f"{current_path}/{item_name}" if current_path else item_name
                )
                subdirectory_results = await _walk_dir(subdir_path, current_depth + 1)
                results.update(subdirectory_results)

        return results

    all_files = await _walk_dir(path, 1)

    if detail:
        return all_files
    else:
        return sorted(all_files.keys())


async def created(self: "AsyncHyphaArtifact", path: str) -> str | None:
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
    return path_info.get("created") if path_info else None


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
    if path_info.get("type") == "directory":
        return 0
    return int(path_info.get("size", 0)) or 0


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
            await self._remote_remove_file(normalize_path(file_path))
    else:
        await self._remote_remove_file(normalize_path(path))


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


async def mkdir(
    self: "AsyncHyphaArtifact",
    path: str,
    create_parents: bool = True,
    **kwargs: Any,
) -> None:
    """Create a directory

    In the Hypha artifact system, directories don't need to be explicitly created,
    they are implicitly created when files are added under a path.
    However, we'll implement this as a no-op to maintain compatibility.

    Parameters
    ----------
    path: str
        Path to create
    create_parents: bool
        If True, create parent directories if they don't exist
    """
    return


async def makedirs(
    self: "AsyncHyphaArtifact",
    path: str,
    exist_ok: bool = True,
    **kwargs: Any,
) -> None:
    """Create a directory tree

    In the Hypha artifact system, directories don't need to be explicitly created,
    they are implicitly created when files are added under a path.

    Parameters
    ----------
    path: str
        Path to create
    exist_ok: bool
        If False and the directory exists, raise an error
    """
    if not exist_ok and await self.exists(path) and await self.isdir(path):
        raise FileExistsError(f"Directory already exists: {path}")
    return


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
        return False
