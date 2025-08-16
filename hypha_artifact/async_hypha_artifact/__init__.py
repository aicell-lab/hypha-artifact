"""Implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha
artifacts using the fsspec specification, allowing for operations like reading,
writing, listing, and manipulating files stored in Hypha artifacts.
"""

import os
from typing import Self

import httpx

from ._fs import (
    created,
    exists,
    find,
    info,
    isdir,
    isfile,
    listdir,
    ls,
    makedirs,
    mkdir,
    rm,
    rm_file,
    rmdir,
    size,
    sizes,
    touch,
)
from ._io import (
    cat,
    copy,
    cp,
    fsspec_open,
    get,
    head,
    put,
)
from ._state import commit, create, delete, discard, edit, list_children


class AsyncHyphaArtifact:
    """Provides an async fsspec-like interface for interacting with Hypha artifact."""

    token: str | None
    workspace: str | None
    artifact_alias: str
    artifact_url: str
    use_proxy: bool | None = None
    use_local_url: bool | None = False
    disable_ssl: bool = False
    _client: httpx.AsyncClient | None

    def __init__(
        self: Self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        server_url: str | None = None,
        *,
        use_proxy: bool | None = None,
        use_local_url: bool | None = None,
        disable_ssl: bool = False,
    ) -> None:
        """Initialize an AsyncHyphaArtifact instance.

        Parameters
        ----------
        artifact_id: str
            The ID of the artifact to interact with.
        workspace: str | None
            The workspace the artifact belongs to (optional).
        token: str | None
            The authentication token to use (optional).
        server_url: str | None
            The URL of the Hypha server (optional).
        use_proxy: bool | None
            Whether to use a proxy (optional).
        use_local_url: bool | None
            Whether to use a local URL (optional).
        disable_ssl: bool
            Whether to disable SSL verification (optional).

        """
        self.artifact_id = artifact_id
        if "/" in artifact_id:
            self.workspace, self.artifact_alias = artifact_id.split("/")
            if workspace and workspace != self.workspace:
                error_msg = f"Workspace mismatch: {workspace} != {self.workspace}"
                raise ValueError(error_msg)
        else:
            if not workspace:
                error_msg = (
                    "Workspace must be provided if artifact_id does not include it"
                )
                raise ValueError(error_msg)
            self.workspace = workspace
            self.artifact_alias = artifact_id
        self.token = token
        if server_url:
            self.artifact_url = f"{server_url}/public/services/artifact-manager"
        else:
            error_msg = "Server URL must be provided, e.g. https://hypha.aicell.io"
            raise ValueError(error_msg)
        self._client = None
        self.ssl = False if disable_ssl else None

        env_proxy = os.getenv("HYPHA_USE_PROXY")
        if use_proxy is not None:
            self.use_proxy = use_proxy
        elif env_proxy is not None:
            self.use_proxy = env_proxy.lower() == "true"
        else:
            self.use_proxy = None

        env_local_url = os.getenv("HYPHA_USE_LOCAL_URL")
        if use_local_url is not None:
            self.use_local_url = use_local_url
        elif env_local_url is not None:
            self.use_local_url = env_local_url.lower() == "true"
        else:
            self.use_local_url = None

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(verify=bool(self.ssl), timeout=60.0)
        return self

    async def __aexit__(
        self: Self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.aclose()

    async def aclose(self: Self) -> None:
        """Explicitly close the httpx client and clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_client(self: Self) -> httpx.AsyncClient:
        """Get or create httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(verify=bool(self.ssl))
        return self._client

    create = create
    delete = delete
    edit = edit
    commit = commit
    list_children = list_children
    cat = cat
    open = fsspec_open
    copy = copy
    cp = cp
    get = get
    put = put
    head = head
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
    touch = touch
    discard = discard
