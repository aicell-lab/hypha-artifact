"""Implements an fsspec-compatible interface for Hypha artifacts.

This module provides an async file-system like interface to interact with remote Hypha
artifacts using the fsspec specification, allowing for operations like reading,
writing, listing, and manipulating files stored in Hypha artifacts.
"""

from typing import Self

import httpx

from ._fs import (
    exists,
    find,
    info,
    isdir,
    isfile,
    listdir,
    ls,
    makedirs,
    mkdir,
    modified,
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
from ._utils import env_override


class AsyncHyphaArtifact:
    """Provides an async fsspec-like interface for interacting with Hypha artifact."""

    token: str | None
    workspace: str | None
    artifact_alias: str
    artifact_url: str
    use_proxy: bool | None = None
    use_local_url: bool | str | None = False
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
        use_local_url: bool | str | None = None,
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
        use_local_url: bool | str | None
            If True, use a generated local URL.
            If False, use a remote URL.
            If is string, use specified local URL (optional).
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

        should_use_proxy = env_override("HYPHA_USE_PROXY", override=use_proxy)

        if isinstance(should_use_proxy, str):
            error_msg = "Invalid type for HYPHA_USE_PROXY: str"
            raise TypeError(error_msg)

        self.use_proxy = should_use_proxy
        self.use_local_url = env_override("HYPHA_USE_LOCAL_URL", override=use_local_url)

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        verify_opt = self.ssl if self.ssl is not None else True
        self._client = httpx.AsyncClient(
            verify=verify_opt,
            timeout=60.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
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
            verify_opt = self.ssl if self.ssl is not None else True
            self._client = httpx.AsyncClient(
                verify=verify_opt,
                timeout=60.0,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
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
    modified = modified
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
