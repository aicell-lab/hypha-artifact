"""
HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides a file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

import json
from typing import Literal, Self, overload, Any
import requests
from hypha_artifact.utils import (
    remove_none,
    parent_and_filename,
    FileMode,
    OnError,
    JsonType,
)
from hypha_artifact.artifact_file import ArtifactHttpFile


class HyphaArtifact:
    """
    HyphaArtifact provides an fsspec-like interface for interacting with Hypha artifact storage.

    This class allows users to manage files and directories within a Hypha artifact,
    including uploading, downloading, editing metadata, listing contents, and managing permissions.
    It abstracts the underlying HTTP API and
    provides a file-system-like interface compatible with fsspec.

    Attributes
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
    >>> artifact = HyphaArtifact("my-artifact", "workspace-id", "my-token")
    >>> artifact.ls("/")
    ['data.csv', 'images/']
    >>> with artifact.open("data.csv", "r") as f:
    ...     print(f.read())
    >>> with artifact.open("data.csv", "w") as f:
    ...     f.write("new content")
    """

    artifact_alias: str
    artifact_url: str
    token: str
    workspace_id: str

    def __init__(self: Self, artifact_alias: str, workspace: str, token: str):
        """Initialize a HyphaArtifact instance.

        Parameters
        ----------
        artifact_id: str
            The identifier of the Hypha artifact to interact with
        """
        self.artifact_alias = artifact_alias
        self.workspace_id = workspace
        self.token = token
        self.artifact_url = "https://hypha.aicell.io/public/services/artifact-manager"

    def _extend_params(
        self: Self,
        params: dict[str, JsonType],
    ) -> dict[str, JsonType]:
        params["artifact_id"] = self.artifact_alias

        return params

    def _remote_request(
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

        response = requests.request(
            method,
            request_url,
            json=cleaned_params if json_data else None,
            params=cleaned_params if params else None,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=20,
        )

        response.raise_for_status()

        return response.content

    def _remote_post(self: Self, method_name: str, params: dict[str, Any]) -> bytes:
        """Make a POST request to the artifact service with extended parameters.

        Returns:
            For put_file requests, returns the pre-signed URL as a string.
            For other requests, returns the response content.
        """
        return self._remote_request(
            method_name,
            method="POST",
            json_data=params,
        )

    def _remote_get(self: Self, method_name: str, params: dict[str, Any]) -> bytes:
        """Make a GET request to the artifact service with extended parameters.

        Returns:
            The response content.
        """
        return self._remote_request(
            method_name,
            method="GET",
            params=params,
        )

    def _remote_edit(
        self: Self,
        manifest: dict[str, Any] | None = None,
        type: str | None = None,
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
            type (str | None): The type of the artifact (e.g., "generic", "collection").
            config (dict[str, Any] | None): Configuration dictionary for the artifact.
            secrets (dict[str, str] | None): Secrets to store with the artifact.
            version (str | None): The version to edit or create.
                Can be "new" for a new version, "stage", or a specific version string.
            comment (str | None): A comment for this version or edit.
            stage (bool): If True, edits are made to a staging version.
        """

        params: dict[str, Any] = {
            "manifest": manifest,
            "type": type,
            "config": config,
            "secrets": secrets,
            "version": version,
            "comment": comment,
            "stage": stage,
        }
        self._remote_post("edit", params)

    def _remote_commit(
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
        self._remote_post("commit", params)

    def _remote_put_file_url(
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
        response_content = self._remote_post("put_file", params)
        return response_content.decode()

    def _remote_remove_file(
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
        self._remote_post("remove_file", params)

    def _remote_get_file_url(
        self: Self,
        path: str,
        silent: bool = False,
        version: str | None = None,
        limit: int = 1000,
    ) -> str:
        """Generates a pre-signed URL to download a file from the artifact stored in S3.

        Args:
            self (Self): The instance of the HyphaArtifact class.
            path (str): The relative path of the file to be downloaded (e.g., "data.csv").
            silent (bool, optional): A boolean to suppress the download count increment.
                Default is False.
            version (str | None, optional): The version of the artifact to download from.
            limit (int, optional): The maximum number of items to return.
                Default is 1000.

        Returns:
            str: A pre-signed URL for downloading the file.
        """
        params: dict[str, str | bool | float | None] = {
            "path": path,
            "silent": silent,
            "version": version,
            "limit": limit,
        }
        response = self._remote_get("get_file", params)
        return response.decode("utf-8")

    def _remote_list_contents(
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
        response_content = self._remote_get("list_files", params)
        return json.loads(response_content)

    @overload
    def cat(
        self: Self,
        path: list[str],
        recursive: bool = False,
        on_error: OnError = "raise",
    ) -> dict[str, str | None]: ...

    @overload
    def cat(
        self: Self, path: str, recursive: bool = False, on_error: OnError = "raise"
    ) -> str | None: ...

    def cat(
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
            result: dict[str, str | None] = {}
            for p in path:
                try:
                    result[p] = self.cat(p, recursive=recursive, on_error=on_error)
                except (FileNotFoundError, IOError, requests.RequestException) as e:
                    if on_error == "raise":
                        raise e
            return result

        # Handle recursive case
        if recursive and self.isdir(path):
            files = self.find(path, maxdepth=None)
            return {p: self.cat(p, on_error=on_error) for p in files}

        # Handle single file case
        try:
            with self.open(path, mode="r") as file:
                content = file.read()
                # Ensure we return a string
                if isinstance(content, bytes):
                    return content.decode("utf-8")
                elif isinstance(content, (bytearray, memoryview)):
                    return bytes(content).decode("utf-8")
                return str(content)
        except (FileNotFoundError, IOError, requests.RequestException) as e:
            if on_error == "raise":
                raise e
            return None

    def open(
        self: Self,
        urlpath: str,
        mode: FileMode = "rb",
        auto_commit: bool = True,
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> ArtifactHttpFile:
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
        ArtifactHttpFile
            A file-like object
        """
        normalized_path = urlpath[1:] if urlpath.startswith("/") else urlpath

        if "r" in mode:
            download_url = self._remote_get_file_url(normalized_path)
            return ArtifactHttpFile(
                url=download_url,
                mode=mode,
                name=normalized_path,
                **kwargs,
            )
        elif "w" in mode or "a" in mode:
            if auto_commit:
                self._remote_edit(stage=True)
            upload_url = self._remote_put_file_url(normalized_path)
            file_obj = ArtifactHttpFile(
                url=upload_url,
                mode=mode,
                name=normalized_path,
                **kwargs,
            )

            if auto_commit:
                file_obj.on_close = self._remote_commit

            return file_obj
        else:
            raise ValueError(f"Unsupported file mode: {mode}")

    def copy(
        self: Self,  # pylint: disable=unused-argument
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        on_error: OnError | None = "raise",
        **kwargs: dict[str, Any],
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
        self._remote_edit(stage=True)
        # Handle recursive case
        if recursive and self.isdir(path1):
            files = self.find(path1, maxdepth=maxdepth)
            for file_path in files:
                # Calculate the destination path
                rel_path = file_path[len(path1) :].lstrip("/")
                dest_path = f"{path2}/{rel_path}" if path2 else rel_path
                try:
                    self._copy_single_file(file_path, dest_path)
                except (FileNotFoundError, IOError, requests.RequestException) as e:
                    if on_error == "raise":
                        raise e
        else:
            # Copy a single file
            self._copy_single_file(path1, path2)

        self._remote_commit()

    def _copy_single_file(self, src: str, dst: str) -> None:
        """Helper method to copy a single file"""
        content = self.cat(src)
        if content is not None:
            with self.open(dst, mode="w", auto_commit=False) as f:
                f.write(content)

    def cp(
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
        return self.copy(
            path1, path2, recursive=recursive, maxdepth=maxdepth, on_error=on_error
        )

    def rm(
        self: Self,
        path: str,
        recursive: bool = False,  # pylint: disable=unused-argument
        maxdepth: int | None = None,  # pylint: disable=unused-argument
    ) -> None:
        """Remove a file from the artifact

        Parameters
        ----------
        path: str
            Path to the file to remove
        recursive: bool, optional
            Not used, included for fsspec compatibility
        maxdepth: int or None, optional
            Not used, included for fsspec compatibility

        Returns
        -------
        None
        """
        self._remote_edit(stage=True)
        self._remote_remove_file(path)
        self._remote_commit()

    def created(self: Self, path: str):
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
        info = self.info(path)
        # Return creation time if available in the metadata, otherwise None
        return info.get("created") if info else None

    def delete(
        self: Self, path: str, recursive: bool = False, maxdepth: int | None = None
    ):
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
        return self.rm(path, recursive, maxdepth)

    def exists(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
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
            with self.open(path, "r") as f:
                partial_content = f.read(0)
                if isinstance(partial_content, (bytes, str)):
                    return True
                return False
        except (FileNotFoundError, IOError, requests.RequestException):
            return False

    def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: bool = True,
        **kwargs: Any,
    ) -> list[str | dict[str, Any]]:
        """List files and directories in a directory

        Parameters
        ----------
        path: str
            Path to list
        detail: bool
            If True, return a list of dictionaries with file details
            If False, return a list of file paths

        Returns
        -------
        list
            List of files and directories in the directory
        """
        result: list[JsonType] = self._remote_list_contents(path)

        if not detail:
            return [
                str(item.get("name", "")) if isinstance(item, dict) else ""
                for item in result
            ]

        # Convert to proper return type
        return [item if isinstance(item, (str, dict)) else {} for item in result]

    def info(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
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
        parent_path, filename = parent_and_filename(path)

        if parent_path is None:
            parent_path = ""

        listing = self.ls(parent_path)
        for item in listing:
            if isinstance(item, dict) and item.get("name") == filename:
                # It's a file
                return item
            elif isinstance(item, str) and item == filename:
                # Return basic info for string items
                return {"name": filename, "type": "file"}

        raise FileNotFoundError(f"Path not found: {path}")

    def isdir(self: Self, path: str) -> bool:
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
            info = self.info(path)
            return info["type"] == "directory"
        except (FileNotFoundError, KeyError):
            return False

    def isfile(self: Self, path: str) -> bool:
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
            info = self.info(path)
            return info["type"] == "file"
        except (FileNotFoundError, KeyError):
            return False

    def listdir(
        self: Self, path: str, **kwargs: Any
    ) -> list[str]:  # pylint: disable=unused-argument
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
        result = self.ls(path, detail=False, **kwargs)
        return [str(item) for item in result]

    def find(
        self: Self,  # pylint: disable=unused-argument
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

        # Helper function to walk the directory tree recursively
        def _walk_dir(
            current_path: str, current_depth: int
        ) -> dict[str, dict[str, Any]]:
            results: dict[str, dict[str, Any]] = {}

            # List current directory
            try:
                items = self.ls(current_path)
            except (FileNotFoundError, IOError, requests.RequestException):
                return {}

            # Add items to results
            for item in items:
                if isinstance(item, dict):
                    item_type = item.get("type")
                    item_name = item.get("name")
                else:
                    # Default values for non-dict items
                    item_type = "file"
                    item_name = str(item)

                if (
                    (item_type == "file" or (withdirs and item_type == "directory"))
                    and isinstance(item, dict)
                    and isinstance(item_name, str)
                ):
                    results[item_name] = item

                # Recurse into subdirectories if depth allows
                if (
                    item_type == "directory"
                    and (maxdepth is None or current_depth < maxdepth)
                    and isinstance(item_name, str)
                ):
                    subdirectory_results = _walk_dir(item_name, current_depth + 1)
                    results.update(subdirectory_results)

            return results

        # Start the recursive walk
        all_files = _walk_dir(path, 1)

        if detail:
            return all_files
        else:
            return sorted(all_files.keys())

    def mkdir(
        self: Self,
        path: str,
        create_parents: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
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
        # Directories in Hypha artifacts are implicit
        # This is a no-op for compatibility with fsspec

    def makedirs(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        exist_ok: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create a directory and any parent directories

        In the Hypha artifact system, directories don't need to be explicitly created,
        they are implicitly created when files are added under a path.
        However, we'll implement this as a no-op to maintain compatibility.

        Parameters
        ----------
        path: str
            Path to create
        exist_ok: bool
            If False and the directory exists, raise an error
        """
        # If the directory already exists and exist_ok is False, raise an error
        if not exist_ok and self.exists(path) and self.isdir(path):
            raise FileExistsError(f"Directory already exists: {path}")

    def rm_file(self: Self, path: str) -> None:
        """Remove a file

        Parameters
        ----------
        path: str
            Path to remove
        """
        self.rm(path)

    def rmdir(self: Self, path: str) -> None:
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
        # Check if the directory exists
        if not self.isdir(path):
            raise FileNotFoundError(f"Directory not found: {path}")

        # Check if the directory is empty
        files = self.ls(path)
        if files:
            raise OSError(f"Directory not empty: {path}")

        # If we get here, the directory is empty (or doesn't exist),
        # so there's nothing to do

    def head(self: Self, path: str, size: int = 1024) -> bytes:
        """Get the first bytes of a file

        Parameters
        ----------
        path: str
            Path to the file
        size: int
            Number of bytes to read

        Returns
        -------
        bytes
            First bytes of the file
        """
        with self.open(path, mode="rb") as f:
            data = f.read(size)
            if isinstance(data, str):
                return data.encode("utf-8")
            return data

    def size(self: Self, path: str) -> int:
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
        info = self.info(path)
        if info["type"] == "directory":
            return 0
        return int(info.get("size", 0)) or 0  # Default to 0 if size is None

    def sizes(self: Self, paths: list[str]) -> list[int]:
        """Get the size of multiple files

        Parameters
        ----------
        paths: list of str
            Paths to the files

        Returns
        -------
        list of int
            Sizes of the files in bytes
        """
        return [self.size(path) for path in paths]
