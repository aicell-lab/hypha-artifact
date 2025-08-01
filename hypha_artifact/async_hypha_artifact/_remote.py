"""Private methods for handling remote HTTP requests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

from ..utils import JsonType, remove_none

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


def extend_params(
    self: "AsyncHyphaArtifact",
    params: dict[str, JsonType],
) -> dict[str, JsonType]:
    """Extend parameters with artifact_id."""
    params["artifact_id"] = (
        f"{self.workspace}/{self.artifact_alias}"
        if self.workspace
        else self.artifact_alias
    )
    return params


async def remote_request(
    self: "AsyncHyphaArtifact",
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
    extended_params = extend_params(self, params or json_data or {})
    cleaned_params = remove_none(extended_params)

    request_url = f"{self.artifact_url}/{artifact_method}"
    client = self.get_client()

    response = await client.request(
        method,
        request_url,
        json=cleaned_params if json_data else None,
        params=cleaned_params if params else None,
        headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
        timeout=20,
    )

    response.raise_for_status()
    return response.content


async def remote_post(
    self: "AsyncHyphaArtifact", method_name: str, params: dict[str, Any]
) -> bytes:
    """Make a POST request to the artifact service with extended parameters.

    Returns:
        For put_file requests, returns the pre-signed URL as a string.
        For other requests, returns the response content.
    """
    return await remote_request(
        self,
        method_name,
        method="POST",
        json_data=params,
    )


async def remote_get(
    self: "AsyncHyphaArtifact", method_name: str, params: dict[str, Any]
) -> bytes:
    """Make a GET request to the artifact service with extended parameters.

    Returns:
        The response content.
    """
    return await remote_request(
        self,
        method_name,
        method="GET",
        params=params,
    )


async def remote_put_file_url(
    self: "AsyncHyphaArtifact",
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
    params: dict[str, str | float | bool | None] = {
        "file_path": file_path,
        "download_weight": download_weight,
        "use_proxy": self.use_proxy,
    }
    response_content = await remote_post(self, "put_file", params)
    return response_content.decode().strip('"')


async def remote_put_file_start_multipart(
    self: "AsyncHyphaArtifact",
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
    response_content = await remote_post(self, "put_file_start_multipart", params)
    return json.loads(response_content.decode())


async def remote_put_file_complete_multipart(
    self: "AsyncHyphaArtifact",
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
    await remote_post(self, "put_file_complete_multipart", params)


async def remote_remove_file(
    self: "AsyncHyphaArtifact",
    file_path: str,
) -> None:
    """Removes a file from the artifact's staged version.

    The artifact must be in staging mode. This operation updates the
    staged manifest.

    Args:
        file_path (str): The path of the file to remove within the artifact.
    """
    params: dict[str, str] = {
        "file_path": file_path,
    }
    await remote_post(self, "remove_file", params)


async def remote_get_file_url(
    self: "AsyncHyphaArtifact",
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
    params: dict[str, str | str | bool | float | None] = {
        "file_path": file_path,
        "silent": silent,
        "version": version,
        "use_proxy": self.use_proxy,
    }
    response_content = await remote_get(self, "get_file", params)
    return json.loads(response_content)


async def remote_list_contents(
    self: "AsyncHyphaArtifact",
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
    params: dict[str, str | str | int | None] = {
        "dir_path": dir_path,
        "limit": limit,
        "version": version,
    }
    response_content = await remote_get(self, "list_files", params)
    return json.loads(response_content)
