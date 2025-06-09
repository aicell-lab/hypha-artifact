"""
Async HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

import json
from typing import Literal, Self, overload, Any
import httpx
from hypha_artifact.utils import (
    remove_none,
    parent_and_filename,
    FileMode,
    OnError,
    JsonType,
)
from hypha_artifact.async_artifact_file import AsyncArtifactHttpFile


class AsyncHyphaArtifact:
    """
    AsyncHyphaArtifact provides an async fsspec-like interface for interacting with Hypha artifact storage.

    This class allows users to manage files and directories within a Hypha artifact,
    including uploading, downloading, editing metadata, listing contents, and managing permissions.
    It abstracts the underlying HTTP API and provides a file-system-like interface compatible with fsspec.

    The class uses a persistent httpx.AsyncClient for efficiency. For best performance and proper
    resource management, use it as an async context manager or call close() explicitly when done.

    Attributes
    ----------
    artifact_alias : str
        The identifier or alias of the Hypha artifact to interact with.
    artifact_url : str
        The base URL for the Hypha artifact manager service.
    token : str
        The authentication token for accessing the artifact service.
    workspace_id : str
        The workspace identifier associated with the artifact.

    Examples
    --------
    Using as an async context manager (recommended):
    >>> async with AsyncHyphaArtifact("my-artifact", "workspace-id", "my-token") as artifact:
    ...     files = await artifact.ls("/")
    ...     async with artifact.open("data.csv", "r") as f:
    ...         content = await f.read()

    Or with explicit cleanup:
    >>> artifact = AsyncHyphaArtifact("my-artifact", "workspace-id", "my-token")
    >>> try:
    ...     files = await artifact.ls("/")
    ...     async with artifact.open("data.csv", "w") as f:
    ...         await f.write("new content")
    ... finally:
    ...     await artifact.aclose()
    """

    artifact_alias: str
    artifact_url: str
    token: str
    workspace_id: str

    def __init__(self: Self, artifact_alias: str, workspace: str, token: str):
        """Initialize an AsyncHyphaArtifact instance.

        Parameters
        ----------
        artifact_id: str
            The identifier of the Hypha artifact to interact with
        """
        self.artifact_alias = artifact_alias
        self.workspace_id = workspace
        self.token = token
        self.artifact_url = "https://hypha.aicell.io/public/services/artifact-manager"
        self._client = None

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self: Self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.aclose()

    async def aclose(self: Self) -> None:
        """Explicitly close the httpx client and clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self: Self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    def _extend_params(
        self: Self,
        params: dict[str, JsonType],
    ) -> dict[str, JsonType]:
        params["artifact_id"] = self.artifact_alias
        return params

    async def _remote_request(
        self: Self,
        artifact_method: str,
        method: Literal["GET", "POST"],
        params: dict[str, JsonType] | None = None,
        json_data: dict[str, JsonType] | None = None,
    ) -> bytes | Any:
        """Make a remote request to the artifact service.
        Args:
            method_name (str): The name of the method to call on the artifact service.
            method (Literal["GET", "POST"]): The HTTP method to use for the request.
            params (dict[str, JsonType] | None): Optional. Parameters to include in the request.
            json (dict[str, JsonType] | None): Optional. JSON body to include in the request.
        Returns:
            str: The response content from the artifact service.
        """
        extended_params = self._extend_params(params or json_data or {})
        cleaned_params = remove_none(extended_params)

        request_url = f"{self.artifact_url}/{artifact_method}"
        client = self._get_client()

        response = await client.request(
            method,
            request_url,
            json=cleaned_params if json_data else None,
            params=cleaned_params if params else None,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=20,
        )

        response.raise_for_status()
        return response.content

    async def _remote_post(
        self: Self, method_name: str, params: dict[str, Any]
    ) -> bytes:
        """Make a POST request to the artifact service with extended parameters.

        Returns:
            For put_file requests, returns the pre-signed URL as a string.
            For other requests, returns the response content.
        """
        return await self._remote_request(
            method_name,
            method="POST",
            json_data=params,
        )

    async def _remote_get(
        self: Self, method_name: str, params: dict[str, Any]
    ) -> bytes:
        """Make a GET request to the artifact service with extended parameters.

        Returns:
            The response content.
        """
        return await self._remote_request(
            method_name,
            method="GET",
            params=params,
        )

    async def _remote_edit(
        self: Self,
        manifest: dict[str, Any] | None = None,
        artifact_type: str | None = None,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
        version: str | None = None,
        comment: str | None = None,
        stage: bool = False,
    ) -> None:
        """Edits the artifact's metadata and saves it.

        This includes the manifest, type, configuration, secrets, and versioning information.

        Args:
            manifest (dict[str, Any] | None): The manifest data to set for the artifact.
            artifact_type (str | None): The type of the artifact (e.g., "generic", "collection").
            config (dict[str, Any] | None): Configuration dictionary for the artifact.
            secrets (dict[str, str] | None): Secrets to store with the artifact.
            version (str | None): The version to edit or create.
                Can be "new" for a new version, "stage", or a specific version string.
            comment (str | None): A comment for this version or edit.
            stage (bool): If True, edits are made to a staging version.
        """

        params: dict[str, Any] = {
            "manifest": manifest,
            "type": artifact_type,
            "config": config,
            "secrets": secrets,
            "version": version,
            "comment": comment,
            "stage": stage,
        }
        await self._remote_post("edit", params)

    async def _remote_commit(
        self: Self,
        version: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Commits the staged changes to the artifact.

        This finalizes the staged manifest and files, creating a new version or
        updating an existing one.

        Args:
            version (str | None): The version string for the commit.
                If None, a new version is typically created. Cannot be "stage".
            comment (str | None): A comment describing the commit.
        """
        params: dict[str, str | None] = {
            "version": version,
            "comment": comment,
        }
        await self._remote_post("commit", params)

    async def _remote_put_file_url(
        self: Self,
        file_path: str,
        download_weight: float = 1.0,
    ) -> str:
        """Requests a pre-signed URL to upload a file to the artifact.

        The artifact must be in staging mode to upload files.

        Args:
            file_path (str): The path within the artifact where the file will be stored.
            download_weight (float): The download weight for the file (default is 1.0).

        Returns:
            str: A pre-signed URL for uploading the file.
        """
        params: dict[str, Any] = {
            "file_path": file_path,
            "download_weight": download_weight,
        }
        response_content = await self._remote_post("put_file", params)
        return response_content.decode()

    async def _remote_remove_file(
        self: Self,
        file_path: str,
    ) -> None:
        """Removes a file from the artifact's staged version.

        The artifact must be in staging mode. This operation updates the
        staged manifest.

        Args:
            file_path (str): The path of the file to remove within the artifact.
        """
        params: dict[str, Any] = {
            "file_path": file_path,
        }
        await self._remote_post("remove_file", params)

    async def _remote_get_file_url(
        self: Self,
        file_path: str,
        silent: bool = False,
        version: str | None = None,
    ) -> str:
        """Generates a pre-signed URL to download a file from the artifact stored in S3.

        Args:
            self (Self): The instance of the AsyncHyphaArtifact class.
            file_path (str): The relative path of the file to be downloaded (e.g., "data.csv").
            silent (bool, optional): A boolean to suppress the download count increment.
                Default is False.
            version (str | None, optional): The version of the artifact to download from.
            limit (int, optional): The maximum number of items to return.
                Default is 1000.

        Returns:
            str: A pre-signed URL for downloading the file.
        """
        params: dict[str, str | bool | float | None] = {
            "file_path": file_path,
            "silent": silent,
            "version": version,
        }
        response = await self._remote_get("get_file", params)
        return response.decode("utf-8")

    async def _remote_list_contents(
        self: Self,
        dir_path: str | None = None,
        limit: int = 1000,
        version: str | None = None,
    ) -> list[JsonType]:
        """Lists files and directories within a specified path in the artifact.

        Args:
            dir_path (str | None): The directory path within the artifact to list.
                If None, lists contents from the root of the artifact.
            limit (int): The maximum number of items to return (default is 1000).
            version (str | None): The version of the artifact to list files from.
                If None, uses the latest committed version. Can be "stage".

        Returns:
            list[JsonType]: A list of items (files and directories) found at the path.
                Each item is a dictionary with details like 'name', 'type', 'size'.
        """
        params: dict[str, Any] = {
            "dir_path": dir_path,
            "limit": limit,
            "version": version,
        }
        response_content = await self._remote_get("list_files", params)
        return json.loads(response_content)

    @overload
    async def cat(
        self: Self,
        path: list[str],
        recursive: bool = False,
        on_error: OnError = "raise",
    ) -> dict[str, str | None]: ...

    @overload
    async def cat(
        self: Self, path: str, recursive: bool = False, on_error: OnError = "raise"
    ) -> str | None: ...

    async def cat(
        self: Self,
        path: str | list[str],
        recursive: bool = False,
        on_error: OnError = "raise",
    ) -> dict[str, str | None] | str | None:
        """Get file(s) content as string(s)

        Parameters
        ----------
        path: str or list of str
            File path(s) to get content from
        recursive: bool
            If True and path is a directory, get all files content
        on_error: "raise" or "ignore"
            What to do if a file is not found

        Returns
        -------
        str or dict or None
            File contents as string if path is a string, dict of {path: content} if path is a list,
            or None if the file is not found and on_error is "ignore"
        """
        # Handle the case where path is a list of paths
        if isinstance(path, list):
            results: dict[str, str | None] = {}
            for p in path:
                results[p] = await self.cat(p, recursive=recursive, on_error=on_error)
            return results

        # Handle recursive case
        if recursive and await self.isdir(path):
            results = {}
            files = await self.find(path, withdirs=False)
            for file_path in files:
                results[file_path] = await self.cat(file_path, on_error=on_error)
            return results

        # Handle single file case
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

    def open(
        self: Self,
        urlpath: str,
        mode: FileMode = "rb",
        auto_commit: bool = True,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> AsyncArtifactHttpFile:
        """Open a file for reading or writing

        Parameters
        ----------
        urlpath: str
            Path to the file within the artifact
        mode: FileMode
            File mode, one of 'r', 'rb', 'w', 'wb', 'a', 'ab'
        auto_commit: bool
            If True, automatically commit changes when the file is closed

        Returns
        -------
        AsyncArtifactHttpFile
            A file-like object
        """
        normalized_path = urlpath[1:] if urlpath.startswith("/") else urlpath

        if "r" in mode:

            async def get_url():
                return await self._remote_get_file_url(normalized_path)

        elif "w" in mode or "a" in mode:

            async def get_url():
                await self._remote_edit(stage=True)
                url = await self._remote_put_file_url(normalized_path)
                return url

        else:
            raise ValueError(f"Unsupported mode: {mode}")

        return AsyncArtifactHttpFile(
            get_url,
            mode=mode,
            name=normalized_path,
            auto_commit=auto_commit,
            commit_func=self._remote_commit if auto_commit else None,
        )

    async def copy(
        self: Self,
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        on_error: OnError | None = "raise",
        **kwargs: dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        """Copy file(s) from path1 to path2 within the artifact

        Parameters
        ----------
        path1: str
            Source path
        path2: str
            Destination path
        recursive: bool
            If True and path1 is a directory, copy all its contents recursively
        maxdepth: int or None
            Maximum recursion depth when recursive=True
        on_error: "raise" or "ignore"
            What to do if a file is not found
        """
        await self._remote_edit(stage=True)
        # Handle recursive case
        if recursive and await self.isdir(path1):
            files = await self.find(path1, maxdepth=maxdepth, withdirs=False)
            for src_file in files:
                rel_path = src_file[len(path1) :].lstrip("/")
                dst_file = f"{path2}/{rel_path}" if rel_path else path2
                await self._copy_single_file(src_file, dst_file)
        else:
            await self._copy_single_file(path1, path2)

        await self._remote_commit()

    async def _copy_single_file(self, src: str, dst: str) -> None:
        """Helper method to copy a single file"""
        content = await self.cat(src)
        if content is not None:
            async with self.open(dst, "w", auto_commit=False) as f:
                await f.write(content)

    async def cp(
        self: Self,
        path1: str,
        path2: str,
        on_error: OnError | None = None,
        **kwargs: Any,
    ) -> None:
        """Alias for copy method

        Parameters
        ----------
        path1: str
            Source path
        path2: str
            Destination path
        on_error: "raise" or "ignore", optional
            What to do if a file is not found
        **kwargs:
            Additional arguments passed to copy method

        Returns
        -------
        None
        """
        recursive = kwargs.pop("recursive", False)
        maxdepth = kwargs.pop("maxdepth", None)
        return await self.copy(
            path1, path2, recursive=recursive, maxdepth=maxdepth, on_error=on_error
        )

    async def rm(
        self: Self,
        path: str,
        recursive: bool = False,  # pylint: disable=unused-argument
        maxdepth: int | None = None,  # pylint: disable=unused-argument
    ) -> None:
        """Remove file or directory"""
        await self._remote_edit(stage=True)
        await self._remote_remove_file(path)
        await self._remote_commit()

    async def created(self: Self, path: str):  # pylint: disable=unused-argument
        """Return creation time of file (not supported, returns None)"""
        return None

    async def delete(
        self: Self,
        path: str,
        recursive: bool = False,  # pylint: disable=unused-argument
        maxdepth: int | None = None,  # pylint: disable=unused-argument
    ):
        """Alias for rm"""
        return await self.rm(path, recursive=recursive, maxdepth=maxdepth)

    async def exists(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> bool:
        """Check if path exists"""
        try:
            await self.info(path)
            return True
        except (FileNotFoundError, IOError):
            return False

    async def ls(
        self: Self,
        path: str,
        detail: bool = True,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> list[str | dict[str, Any]]:
        """List contents of path"""
        normalized_path = path[1:] if path.startswith("/") else path
        normalized_path = normalized_path if normalized_path else None

        try:
            contents = await self._remote_list_contents(normalized_path)
            if detail:
                return contents  # type: ignore
            else:
                return [item.get("name", "") for item in contents if isinstance(item, dict)]  # type: ignore
        except Exception:  # pylint: disable=broad-except
            # If path doesn't exist or is not a directory, return empty list
            return []

    async def info(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> dict[str, Any]:
        """Get file information"""
        normalized_path = path[1:] if path.startswith("/") else path
        parent_path, filename = parent_and_filename(normalized_path)

        contents = await self._remote_list_contents(parent_path)
        for item in contents:
            if isinstance(item, dict) and item.get("name") == filename:
                return item

        raise FileNotFoundError(f"File not found: {path}")

    async def isdir(self: Self, path: str) -> bool:
        """Check if path is a directory"""
        try:
            info = await self.info(path)
            return info.get("type") == "directory"
        except (FileNotFoundError, IOError):
            return False

    async def isfile(self: Self, path: str) -> bool:
        """Check if path is a file"""
        try:
            info = await self.info(path)
            return info.get("type") == "file"
        except (FileNotFoundError, IOError):
            return False

    async def listdir(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> list[str]:
        """List directory contents (names only)"""
        result = await self.ls(path, detail=False)
        return [item for item in result if isinstance(item, str)]

    async def find(
        self: Self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: bool = False,
        **kwargs: dict[str, Any],  # pylint: disable=unused-argument
    ) -> list[str] | dict[str, dict[str, Any]]:
        """Find files recursively"""
        results = []
        results_detail = {}

        async def _find_recursive(current_path: str, current_depth: int = 0):
            if maxdepth is not None and current_depth >= maxdepth:
                return

            try:
                contents = await self.ls(current_path, detail=True)
                for item in contents:
                    if isinstance(item, dict):
                        item_name = item.get("name", "")
                        item_path = f"{current_path}/{item_name}".strip("/")
                        item_type = item.get("type", "")

                        if item_type == "file":
                            results.append(item_path)
                            if detail:
                                results_detail[item_path] = item
                        elif item_type == "directory":
                            if withdirs:
                                results.append(item_path)
                                if detail:
                                    results_detail[item_path] = item
                            await _find_recursive(item_path, current_depth + 1)
            except Exception:  # pylint: disable=broad-except
                pass  # Skip inaccessible directories

        await _find_recursive(path)

        if detail:
            return results_detail
        return results

    async def mkdir(
        self: Self,
        path: str,  # pylint: disable=unused-argument
        create_parents: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> None:
        """Create directory (no-op for Hypha artifacts)"""
        return  # Directories are created implicitly when files are added

    async def makedirs(
        self: Self,
        path: str,  # pylint: disable=unused-argument
        exist_ok: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> None:
        """Create directories recursively (no-op for Hypha artifacts)"""
        return  # Directories are created implicitly when files are added

    async def rm_file(self: Self, path: str) -> None:
        """Remove a single file"""
        await self.rm(path)

    async def rmdir(self: Self, path: str) -> None:  # pylint: disable=unused-argument
        """Remove directory (no-op for Hypha artifacts)"""
        return  # Directories are removed implicitly when all files are removed

    async def head(self: Self, path: str, size: int = 1024) -> bytes:
        """Read first `size` bytes of file"""
        async with self.open(path, "rb") as f:
            result = await f.read(size)
            if isinstance(result, bytes):
                return result
            elif isinstance(result, str):
                return result.encode()
            else:
                return bytes(result)

    async def size(self: Self, path: str) -> int:
        """Get file size"""
        info = await self.info(path)
        return info.get("size", 0)

    async def sizes(self: Self, paths: list[str]) -> list[int]:
        """Get sizes of multiple files"""
        sizes = []
        for path in paths:
            try:
                size = await self.size(path)
                sizes.append(size)
            except Exception:  # pylint: disable=broad-except
                sizes.append(0)
        return sizes
