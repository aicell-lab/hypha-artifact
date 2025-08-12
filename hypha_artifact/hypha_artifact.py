"""
HyphaArtifact module implements an fsspec-compatible interface for Hypha artifacts.

This module provides a file-system like interface to interact with remote Hypha artifacts
using the fsspec specification, allowing for operations like reading, writing, listing,
and manipulating files stored in Hypha artifacts.
"""

from datetime import datetime
from typing import Callable, Literal, Self, overload, Any, TYPE_CHECKING

from .utils import OnError
from .artifact_file import ArtifactHttpFile
from .async_hypha_artifact import AsyncHyphaArtifact
from .sync_utils import run_sync
from .classes import ArtifactItem

if not TYPE_CHECKING:
    try:
        # Try to import the pyodide-specific run_sync
        from pyodide.ffi import run_sync
    except ImportError:
        # Fallback to the default implementation if pyodide is not available
        pass


class HyphaArtifact:
    """
    HyphaArtifact provides an fsspec-like interface for interacting with Hypha artifact storage.

    This class allows users to manage files and directories within a Hypha artifact,
    including uploading, downloading, editing metadata, listing contents, and managing permissions.
    It abstracts the underlying HTTP API and
    provides a file-system-like interface compatible with fsspec.

    Attributes
    ----------
    artifact_id : str
        The identifier or alias of the Hypha artifact to interact with.
    workspace : str | None
        The workspace identifier associated with the artifact.
    token : str | None
        The authentication token for accessing the artifact service.
    server_url : str | None
        The base URL for the Hypha server.
    use_proxy : bool | None
        Whether to use a proxy for HTTP requests.
    use_local_url : bool | None
        Whether to use a local URL for HTTP requests.

    Examples
    --------
    >>> artifact = HyphaArtifact("artifact-id", "workspace-id", "my-token", "https://hypha.aicell.io/public/services/artifact-manager")
    >>> artifact.ls("/")
    ['data.csv', 'images/']
    >>> with artifact.open("data.csv", "r") as f:
    ...     print(f.read())
    >>> # To write to an artifact, you first need to stage the changes
    >>> artifact.edit(stage=True)
    >>> with artifact.open("data.csv", "w") as f:
    ...     f.write("new content")
    >>> # After making changes, you need to commit them
    >>> artifact.commit(comment="Updated data.csv")
    """

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
        """Initialize a HyphaArtifact instance.

        Parameters
        ----------
        artifact_id: str
            The identifier of the Hypha artifact to interact with
        """
        self._async_artifact = AsyncHyphaArtifact(
            artifact_id,
            workspace=workspace,
            token=token,
            server_url=server_url,
            use_proxy=use_proxy,
            use_local_url=use_local_url,
            disable_ssl=disable_ssl,
        )

    def edit(
        self: Self,
        manifest: dict[str, Any] | None = None,
        type: str | None = None,  # pylint: disable=redefined-builtin
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
        version: str | None = None,
        comment: str | None = None,
        stage: bool = False,
    ) -> None:
        """Edits the artifact's metadata and saves it."""
        return run_sync(
            self._async_artifact.edit(
                manifest=manifest,
                type=type,
                config=config,
                secrets=secrets,
                version=version,
                comment=comment,
                stage=stage,
            )
        )

    def commit(
        self: Self,
        version: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Commits the staged changes to the artifact."""
        return run_sync(self._async_artifact.commit(version, comment))

    def discard(self: Self) -> None:
        """Discards all staged changes for an artifact, reverting to the last committed state."""
        return run_sync(self._async_artifact.discard())

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
        """Get file(s) content as string(s)"""
        return run_sync(self._async_artifact.cat(path, recursive, on_error))

    def open(
        self: Self,
        urlpath: str,
        mode: str = "rb",
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> ArtifactHttpFile:
        """Open a file for reading or writing"""
        async_file = self._async_artifact.open(urlpath, mode, **kwargs)
        url = run_sync(async_file.get_url())

        return ArtifactHttpFile(
            url=url,
            mode=mode,
            name=async_file.name,
            **kwargs,
        )

    def copy(
        self: Self,  # pylint: disable=unused-argument
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        on_error: OnError | None = "raise",
        **kwargs: dict[str, Any],
    ) -> None:
        """Copy file(s) from path1 to path2 within the artifact"""
        return run_sync(
            self._async_artifact.copy(
                path1=path1,
                path2=path2,
                recursive=recursive,
                maxdepth=maxdepth,
                on_error=on_error,
                **kwargs,
            )
        )

    def get(
        self: Self,
        rpath: str | list[str],
        lpath: str | list[str],
        recursive: bool = False,
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        **kwargs: Any,
    ) -> None:
        """Copy file(s) from remote (artifact) to local filesystem"""
        return run_sync(
            self._async_artifact.get(
                rpath=rpath,
                lpath=lpath,
                recursive=recursive,
                callback=callback,
                maxdepth=maxdepth,
                on_error=on_error,
                **kwargs,
            )
        )

    def put(
        self: Self,
        lpath: str | list[str],
        rpath: str | list[str],
        recursive: bool = False,
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        multipart_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Copy file(s) from local filesystem to remote (artifact)"""

        return run_sync(
            self._async_artifact.put(
                lpath=lpath,
                rpath=rpath,
                recursive=recursive,
                callback=callback,
                maxdepth=maxdepth,
                on_error=on_error,
                multipart_config=multipart_config,
                **kwargs,
            )
        )

    def cp(
        self: Self,
        path1: str,
        path2: str,
        on_error: OnError | None = None,
        **kwargs: Any,
    ) -> None:
        """Alias for copy method"""
        return run_sync(self._async_artifact.cp(path1, path2, on_error, **kwargs))

    def rm(
        self: Self,
        path: str,
        recursive: bool = False,
        maxdepth: int | None = None,
    ) -> None:
        """Remove file or directory"""
        return run_sync(self._async_artifact.rm(path, recursive, maxdepth))

    def created(self: Self, path: str) -> datetime | None:
        """Get the creation time of a file"""
        return run_sync(self._async_artifact.created(path))

    def delete(
        self: Self, path: str, recursive: bool = False, maxdepth: int | None = None
    ) -> None:
        """Delete a file or directory from the artifact"""
        return run_sync(self._async_artifact.delete(path, recursive, maxdepth))

    def exists(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> bool:
        """Check if a file or directory exists"""
        return run_sync(self._async_artifact.exists(path, **kwargs))

    @overload
    def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: Literal[False],
        **kwargs: Any,
    ) -> list[str]: ...

    @overload
    def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: None | Literal[True] = True,
        **kwargs: Any,
    ) -> list[ArtifactItem]: ...

    def ls(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        detail: None | bool = True,
        **kwargs: Any,
    ) -> list[str] | list[ArtifactItem]:
        """List files and directories in a directory"""
        return run_sync(self._async_artifact.ls(path, detail, **kwargs))

    def info(
        self: Self, path: str, **kwargs: Any  # pylint: disable=unused-argument
    ) -> ArtifactItem:
        """Get information about a file or directory"""
        return run_sync(self._async_artifact.info(path, **kwargs))

    def isdir(self: Self, path: str) -> bool:
        """Check if a path is a directory"""
        return run_sync(self._async_artifact.isdir(path))

    def isfile(self: Self, path: str) -> bool:
        """Check if a path is a file"""
        return run_sync(self._async_artifact.isfile(path))

    def listdir(
        self: Self, path: str, **kwargs: Any
    ) -> list[str]:  # pylint: disable=unused-argument
        """List files in a directory"""
        return run_sync(self._async_artifact.listdir(path, **kwargs))

    @overload
    def find(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        *,
        detail: Literal[True],
        **kwargs: dict[str, Any],
    ) -> dict[str, ArtifactItem]: ...

    @overload
    def find(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: Literal[False] = False,
        **kwargs: dict[str, Any],
    ) -> list[str]: ...

    def find(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: bool = False,
        **kwargs: dict[str, Any],
    ) -> list[str] | dict[str, ArtifactItem]:
        """Find all files (and optional directories) under a path"""
        return run_sync(
            self._async_artifact.find(
                path, maxdepth=maxdepth, withdirs=withdirs, detail=detail, **kwargs
            )
        )

    def mkdir(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        create_parents: bool = True,  # pylint: disable=unused-argument
        **kwargs: Any,  # pylint: disable=unused-argument
    ) -> None:
        """Create a directory"""
        return run_sync(self._async_artifact.mkdir(path, create_parents, **kwargs))

    def makedirs(
        self: Self,  # pylint: disable=unused-argument
        path: str,
        exist_ok: bool = True,
        **kwargs: Any,
    ) -> None:
        """Create a directory and any parent directories"""
        return run_sync(self._async_artifact.makedirs(path, exist_ok, **kwargs))

    def rm_file(self: Self, path: str) -> None:
        """Remove a file"""
        return run_sync(self._async_artifact.rm_file(path))

    def rmdir(self: Self, path: str) -> None:
        """Remove an empty directory"""
        return run_sync(self._async_artifact.rmdir(path))

    def head(self: Self, path: str, size: int = 1024) -> bytes:
        """Get the first bytes of a file"""
        return run_sync(self._async_artifact.head(path, size))

    def size(self: Self, path: str) -> int:
        """Get the size of a file in bytes"""
        return run_sync(self._async_artifact.size(path))

    def sizes(self: Self, paths: list[str]) -> list[int]:
        """Get the size of multiple files"""
        return run_sync(self._async_artifact.sizes(paths))

    def touch(self: Self, path: str, truncate: bool = True, **kwargs: Any) -> None:
        """Create an empty file or update the timestamp of an existing file"""
        return run_sync(self._async_artifact.touch(path, truncate=truncate, **kwargs))
