"""
Async HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

# TODO: replicate fsspec code implementation as much as possible
import os
from typing import Self, Any

import httpx

# Imported methods
from ._remote import (
    extend_params,
    remote_request,
    remote_post,
    remote_get,
    remote_put_file_url,
    remote_remove_file,
    remote_get_file_url,
    remote_list_contents,
)
from ._state import edit, commit
from ._io import (
    cat,
    fsspec_open,
    copy,
    cp,
    get,
    put,
    head,
    copy_single_file,
    put_single_file,
    get_single_file,
    get_recursive,
    get_list,
    put_list,
)
from ._fs import (
    ls,
    listdir,
    info,
    exists,
    isdir,
    isfile,
    find,
    created,
    size,
    sizes,
    rm,
    delete,
    rm_file,
    mkdir,
    makedirs,
    rmdir,
)


class AsyncHyphaArtifact:
    """
    AsyncHyphaArtifact provides an async fsspec-like interface for interacting with Hypha
    artifact storage.
    """

    token: str | None
    workspace: str | None
    artifact_alias: str
    artifact_url: str
    use_proxy: bool | None = None
    _client: httpx.AsyncClient | None

    def __init__(
        self: Self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        service_url: str | None = None,
        use_proxy: bool | None = None,
    ):
        """Initialize an AsyncHyphaArtifact instance."""
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

        env_proxy = os.getenv("HYPHA_USE_PROXY")
        if use_proxy is not None:
            self.use_proxy = use_proxy
        elif env_proxy is not None:
            self.use_proxy = env_proxy.lower() == "true"
        else:
            self.use_proxy = None

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

    _extend_params = extend_params
    _remote_request = remote_request
    _remote_post = remote_post
    _remote_get = remote_get
    _remote_put_file_url = remote_put_file_url
    _remote_remove_file = remote_remove_file
    _remote_get_file_url = remote_get_file_url
    _remote_list_contents = remote_list_contents
    edit = edit
    commit = commit
    cat = cat
    open = fsspec_open
    copy = copy
    cp = cp
    get = get
    put = put
    head = head
    _copy_single_file = copy_single_file
    _put_single_file = put_single_file
    _get_single_file = get_single_file
    _get_recursive = get_recursive
    _get_list = get_list
    _put_list = put_list
    ls = ls
    listdir = listdir
    info = info
    exists = exists
    isdir = isdir
    isfile = isfile
    find = find
    created = created
    size = size
    sizes = sizes
    rm = rm
    delete = delete
    rm_file = rm_file
    mkdir = mkdir
    makedirs = makedirs
    rmdir = rmdir
