"""
Async HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

import os
from typing import Self, Any

import httpx

from ._state import edit, commit
from ._io import (
    cat,
    fsspec_open,
    copy,
    cp,
    get,
    put,
    head,
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
    touch,
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
    use_local_url: bool | None = None
    disable_ssl: bool = False
    _client: httpx.AsyncClient | None

    def __init__(
        self: Self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        server_url: str | None = None,
        use_proxy: bool | None = None,
        use_local_url: bool | None = None,
        disable_ssl: bool = False,
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
        if server_url:
            self.artifact_url = f"{server_url}/public/services/artifact-manager"
        else:
            raise ValueError(
                "Server URL must be provided, e.g. https://hypha.aicell.io"
            )
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
        self._client = httpx.AsyncClient(verify=bool(self.ssl), timeout=30.0)
        return self

    async def __aexit__(self: Self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
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

    edit = edit
    commit = commit
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
