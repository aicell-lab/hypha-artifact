"""
Async HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

import json
import os
import asyncio
from pathlib import Path
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
    AsyncHyphaArtifact provides an async fsspec-like interface for interacting with Hypha
    artifact storage.

    This class allows users to manage files and directories within a Hypha artifact,
    including uploading, downloading, editing metadata, listing contents, and managing permissions.
    It abstracts the underlying HTTP API and provides a file-system-like interface compatible with
    fsspec.

    The class uses a persistent httpx.AsyncClient for efficiency. For best performance and proper
    resource management, use it as an async context manager or call close() explicitly when done.

    Attributes
    ----------
    artifact_alias : str
        The identifier or alias of the Hypha artifact to interact with.
    workspace : str | None
        The workspace identifier associated with the artifact.
    token : str | None
        The authentication token for accessing the artifact service.
    service_url : str | None
        The base URL for the Hypha artifact manager service.

    Examples
    --------
    Using as an async context manager (recommended):
    >>> async with AsyncHyphaArtifact("my-artifact", "workspace-id", "my-token", "https://hypha.aicell.io/public/services/artifact-manager") as artifact:
    ...     files = await artifact.ls("/")
    ...     async with artifact.open("data.csv", "r") as f:
    ...         content = await f.read()

    Or with explicit cleanup:
    >>> artifact = AsyncHyphaArtifact("my-artifact", "workspace-id", "my-token", "https://hypha.aicell.io/public/services/artifact-manager")
    >>> try:
    ...     files = await artifact.ls("/")
    ...     async with artifact.open("data.csv", "w") as f:
    ...         await f.write("new content")
    ... finally:
    ...     await artifact.aclose()
    """

    token: str | None
    workspace: str | None
    artifact_alias: str
    artifact_url: str
    _client: httpx.AsyncClient | None

    def __init__(
        self: Self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        service_url: str | None = None,
    ):
        """Initialize an AsyncHyphaArtifact instance.

        Parameters
        ----------
        artifact_id: str
            The identifier of the Hypha artifact to interact with
        """
        if "/" in artifact_id:
            self.workspace, self.artifact_alias = artifact_id.split("/")
            if workspace:
                assert workspace == self.workspace, "Workspace mismatch"
        else:
            assert (
                workspace
            ), "Workspace must be provided if artifact_id does not include it"
            self.workspace = workspace
            self.artifact_alias = artifact_id
        self.token = token
        if service_url:
            self.artifact_url = service_url
        else:
            self.artifact_url = (
                "https://hypha.aicell.io/public/services/artifact-manager"
            )
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

    def _normalize_path(self: Self, path: str) -> str:
        """Normalize the path by removing all leading slashes."""
        return path.lstrip("/")

    async def _remote_request(
        self: Self,
        artifact_method: str,
        method: Literal["GET", "POST"],
        params: dict[str, JsonType] | None = None,
        json_data: dict[str, JsonType] | None = None,
    ) -> bytes:
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
        return response_content.decode().strip('"')

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
        return response.decode("utf-8").strip('"')

    async def _remote_put_file_start_multipart(
        self: Self,
        file_path: str,
        part_count: int,
        expires_in: int = 7200,
        download_weight: float = 1.0,
    ) -> dict[str, Any]:
        """Start a multipart upload for a file.

        Args:
            file_path (str): The path within the artifact where the file will be stored.  
            part_count (int): The number of parts for the multipart upload.
            expires_in (int): Expiration time in seconds (default: 7200 = 2 hours).
            download_weight (float): The download weight for the file (default is 1.0).

        Returns:
            dict: Multipart upload information including upload_id and parts.
        """
        params: dict[str, Any] = {
            "file_path": file_path,
            "part_count": part_count,
            "expires_in": expires_in,
            "download_weight": download_weight,
        }
        response_content = await self._remote_post("put_file_start_multipart", params)
        return json.loads(response_content.decode())

    async def _remote_put_file_complete_multipart(
        self: Self,
        upload_id: str,
        parts: list[dict[str, Any]],
    ) -> None:
        """Complete a multipart upload.

        Args:
            upload_id (str): The upload ID from put_file_start_multipart.
            parts (list): List of completed parts with part_number and etag.
        """
        params: dict[str, Any] = {
            "upload_id": upload_id,
            "parts": parts,
        }
        await self._remote_post("put_file_complete_multipart", params)

    async def upload(
        self: Self,
        local_path: str | Path,
        remote_path: str = "",
        recursive: bool = True,
        enable_multipart: bool = False,
        multipart_threshold: int = 100 * 1024 * 1024,  # 100MB
        chunk_size: int = 10 * 1024 * 1024,  # 10MB per part
        max_parallel_uploads: int = 4,
        download_weight: float = 1.0,
        auto_commit: bool = True,
    ) -> None:
        """Upload a file or folder to the artifact with optional multipart upload.

        Parameters
        ----------
        local_path: str or Path
            Path to the local file or folder to upload
        remote_path: str
            Path within the artifact where the content will be stored (default: same name)
        recursive: bool
            Whether to upload subdirectories recursively when uploading folders (default: True)
        enable_multipart: bool
            Force multipart upload even for small files (default: False)
        multipart_threshold: int
            File size threshold for automatic multipart upload (default: 100MB)
        chunk_size: int
            Size of each part in multipart upload (default: 10MB)
        max_parallel_uploads: int
            Maximum number of parallel part uploads (default: 4)
        download_weight: float
            Download weight for files (default: 1.0)
        auto_commit: bool
            Whether to automatically commit after upload (default: True)
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local path does not exist: {local_path}")

        # If no remote_path specified, use the local name
        if not remote_path:
            remote_path = local_path.name

        if local_path.is_file():
            # Upload single file
            file_size = local_path.stat().st_size
            use_multipart = enable_multipart or file_size >= multipart_threshold

            if auto_commit:
                await self._remote_edit(stage=True)

            if use_multipart and file_size > chunk_size:
                await self._upload_multipart(
                    local_path, remote_path, chunk_size, max_parallel_uploads, download_weight
                )
            else:
                await self._upload_single(local_path, remote_path, download_weight)

            if auto_commit:
                await self._remote_commit()

        elif local_path.is_dir():
            # Upload folder
            if auto_commit:
                await self._remote_edit(stage=True)

            try:
                files_to_upload = []
                if recursive:
                    for file_path in local_path.rglob("*"):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(local_path)
                            remote_file_path = f"{remote_path}/{relative_path}".strip("/")
                            files_to_upload.append((file_path, remote_file_path))
                else:
                    for file_path in local_path.iterdir():
                        if file_path.is_file():
                            remote_file_path = f"{remote_path}/{file_path.name}".strip("/")
                            files_to_upload.append((file_path, remote_file_path))

                # Upload files concurrently
                upload_tasks = []
                for local_file_path, remote_file_path in files_to_upload:
                    file_size = local_file_path.stat().st_size
                    use_multipart = enable_multipart or file_size >= multipart_threshold

                    if use_multipart and file_size > chunk_size:
                        task = self._upload_multipart(
                            local_file_path, remote_file_path, chunk_size, max_parallel_uploads, download_weight
                        )
                    else:
                        task = self._upload_single(local_file_path, remote_file_path, download_weight)
                    
                    upload_tasks.append(task)

                # Wait for all uploads to complete
                await asyncio.gather(*upload_tasks)

                if auto_commit:
                    await self._remote_commit()
                    
            except Exception as e:
                raise IOError(f"Folder upload failed: {str(e)}") from e
        else:
            raise ValueError(f"Path is neither a file nor a directory: {local_path}")

    async def _upload_single(
        self: Self,
        local_path: Path,
        remote_path: str,
        download_weight: float = 1.0,
    ) -> None:
        """Upload a file using single upload."""
        upload_url = await self._remote_put_file_url(remote_path, download_weight)
        
        with open(local_path, 'rb') as f:
            content = f.read()
            
        client = self._get_client()
        response = await client.put(
            upload_url,
            content=content,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(content)),
            },
            timeout=300,  # 5 minutes for large files
        )
        response.raise_for_status()

    async def _upload_multipart(
        self: Self,
        local_path: Path,
        remote_path: str,
        chunk_size: int,
        max_parallel_uploads: int,
        download_weight: float = 1.0,
    ) -> None:
        """Upload a file using multipart upload with parallel uploads."""
        import math
        
        # Calculate part count based on file size and chunk size
        file_size = local_path.stat().st_size
        part_count = math.ceil(file_size / chunk_size)
        
        # Start multipart upload
        try:
            multipart_info = await self._remote_put_file_start_multipart(
                remote_path, part_count, download_weight=download_weight
            )
            print(f"DEBUG: Multipart info response: {multipart_info}")  # Temporary debug
            
            upload_id = multipart_info["upload_id"]
            
            # Handle different possible response structures
            if "parts" in multipart_info:
                parts_info = multipart_info["parts"]
            elif "urls" in multipart_info:
                # Alternative structure where URLs might be in a different field
                parts_info = multipart_info["urls"]
            else:
                # If no parts/urls, try to generate part info from upload_id
                # This might be a case where we need to make separate calls for each part URL
                raise ValueError(f"Unexpected multipart response structure: {multipart_info}")

        except Exception as e:
            raise IOError(f"Failed to start multipart upload: {str(e)}") from e

        async def upload_part(part_info: dict[str, Any], chunk_data: bytes) -> dict[str, Any]:
            """Upload a single part."""
            part_number = part_info.get("part_number", parts_info.index(part_info) + 1)
            
            # Handle different possible URL field names
            upload_url = None
            for url_field in ["upload_url", "url", "presigned_url", "uploadUrl"]:
                if url_field in part_info:
                    upload_url = part_info[url_field]
                    break
            
            if not upload_url:
                raise KeyError(f"No upload URL found in part info: {part_info}")

            client = self._get_client()
            response = await client.put(
                upload_url,
                content=chunk_data,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(chunk_data)),
                },
                timeout=300,
            )
            response.raise_for_status()

            # Get ETag from response
            etag = response.headers.get("ETag", "").strip('"')
            return {
                "part_number": part_number,
                "etag": etag
            }

        try:
            # Read all chunks into memory (for smaller files this should be fine)
            chunks = []
            with open(local_path, 'rb') as f:
                for part_info in parts_info:
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    chunks.append((part_info, chunk_data))

            # Upload parts in parallel with semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_parallel_uploads)
            
            async def upload_with_semaphore(part_info_chunk):
                async with semaphore:
                    return await upload_part(part_info_chunk[0], part_info_chunk[1])

            # Upload all parts in parallel
            completed_parts = await asyncio.gather(
                *[upload_with_semaphore(chunk) for chunk in chunks]
            )

            # Complete multipart upload
            await self._remote_put_file_complete_multipart(upload_id, completed_parts)

        except Exception as e:
            # If something goes wrong, we should ideally abort the multipart upload
            # but the API doesn't seem to have an abort endpoint in the docs
            raise IOError(f"Multipart upload failed: {str(e)}") from e



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
        self: Self,  # pylint: disable=unused-argument
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
        normalized_path = self._normalize_path(urlpath)

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
        self: Self,  # pylint: disable=unused-argument
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

        if recursive and await self.isdir(path):
            files = await self.find(
                path, maxdepth=maxdepth, withdirs=False, detail=False
            )
            for file_path in files:
                await self._remote_remove_file(self._normalize_path(file_path))
        else:
            await self._remote_remove_file(self._normalize_path(path))

        await self._remote_commit()

    async def created(self: Self, path: str) -> str | None:
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
        info = await self.info(path)
        # Return creation time if available in the metadata, otherwise None
        return info.get("created") if info else None

    async def delete(
        self: Self, path: str, recursive: bool = False, maxdepth: int | None = None
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

    async def exists(
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
            async with self.open(path, "r") as f:
                await f.read(0)
                return True
        except (FileNotFoundError, IOError, httpx.RequestError):
            return False

    @overload
    async def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: Literal[False],
        **kwargs: Any,
    ) -> list[str]: ...

    @overload
    async def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: Literal[True],
        **kwargs: Any,
    ) -> list[dict[str, Any]]: ...

    @overload
    async def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        **kwargs: Any,
    ) -> list[dict[str, Any]]: ...

    async def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: Literal[True] | Literal[False] = True,
        **kwargs: Any,
    ) -> list[str] | list[dict[str, Any]]:
        """List contents of path"""
        contents = await self._remote_list_contents(self._normalize_path(path))

        if detail:
            return [item for item in contents if isinstance(item, dict)]

        return [item.get("name", "") for item in contents if isinstance(item, dict)]

    async def info(
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
        normalized_path = self._normalize_path(path)
        parent_path, filename = parent_and_filename(normalized_path)

        if parent_path is None:
            parent_path = ""

        listing = await self.ls(parent_path)
        for item in listing:
            if item.get("name") == filename:
                return item

        raise FileNotFoundError(f"Path not found: {path}")

    async def isdir(self: Self, path: str) -> bool:
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
            info = await self.info(path)
            return info.get("type") == "directory"
        except (FileNotFoundError, IOError):
            return False

    async def isfile(self: Self, path: str) -> bool:
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
            info = await self.info(path)
            return info.get("type") == "file"
        except (FileNotFoundError, IOError):
            return False

    async def listdir(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
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
        self: Self,  # pylint: disable=unused-argument
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        *,
        detail: Literal[True],
        **kwargs: dict[str, Any],
    ) -> dict[str, dict[str, Any]]: ...

    @overload
    async def find(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: Literal[False] = False,
        **kwargs: dict[str, Any],
    ) -> list[str]: ...

    async def find(
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
        async def _walk_dir(
            current_path: str, current_depth: int
        ) -> dict[str, dict[str, Any]]:
            results: dict[str, dict[str, Any]] = {}

            # List current directory
            try:
                items = await self.ls(current_path)
            except (FileNotFoundError, IOError, httpx.RequestError):
                return {}

            # Add items to results
            for item in items:
                item_type = item.get("type")
                item_name = item.get("name")

                if (
                    item_type == "file" or (withdirs and item_type == "directory")
                ) and isinstance(item_name, str):
                    results[item_name] = item

                # Recurse into subdirectories if depth allows
                if (
                    item_type == "directory"
                    and (maxdepth is None or current_depth < maxdepth)
                    and isinstance(item_name, str)
                ):
                    subdirectory_results = await _walk_dir(item_name, current_depth + 1)
                    results.update(subdirectory_results)

            return results

        # Start the recursive walk
        all_files = await _walk_dir(path, 1)

        if detail:
            return all_files
        else:
            return sorted(all_files.keys())

    async def mkdir(
        self: Self,  # pylint: disable=unused-argument
        path: str,  # pylint: disable=unused-argument
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
        return

    async def makedirs(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        exist_ok: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
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
        # If the directory already exists and exist_ok is False, raise an error
        if not exist_ok and await self.exists(path) and await self.isdir(path):
            raise FileExistsError(f"Directory already exists: {path}")
        return

    async def rm_file(self: Self, path: str) -> None:
        """Remove a file

        Parameters
        ----------
        path: str
            Path to remove
        """
        await self.rm(path)

    async def rmdir(self: Self, path: str) -> None:
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
        if not await self.isdir(path):
            raise FileNotFoundError(f"Directory not found: {path}")

        # Check if the directory is empty
        files = await self.ls(path)
        if files:
            raise OSError(f"Directory not empty: {path}")

        # If we get here, the directory is empty (or doesn't exist),
        # so there's nothing to do

    async def head(self: Self, path: str, size: int = 1024) -> bytes:
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
        async with self.open(path, "rb") as f:
            result = await f.read(size)
            if isinstance(result, bytes):
                return result
            elif isinstance(result, str):
                return result.encode()
            else:
                return bytes(result)

    async def size(self: Self, path: str) -> int:
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
        info = await self.info(path)
        if info.get("type") == "directory":
            return 0
        return int(info.get("size", 0)) or 0  # Default to 0 if size is None

    async def sizes(self: Self, paths: list[str]) -> list[int]:
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
        sizes: list[int] = []
        for path in paths:
            try:
                size = await self.size(path)
                sizes.append(size)
            except Exception:  # pylint: disable=broad-except
                sizes.append(0)
        return sizes
