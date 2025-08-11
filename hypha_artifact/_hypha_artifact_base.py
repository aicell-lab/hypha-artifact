"""
Provides the abstract base class for Hypha artifacts.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Literal, Self, overload

from .utils import OnError


class HyphaArtifactBase(ABC):
    """Abstract base class for Hypha artifacts."""

    @abstractmethod
    def __init__(
        self: Self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        server_url: str | None = None,
        use_proxy: bool | None = None,
        use_local_url: bool | None = False,
        disable_ssl: bool = False,
    ):
        """Initialize a HyphaArtifact instance."""
        raise NotImplementedError

    @abstractmethod
    def edit(
        self: Self,
        manifest: dict[str, Any] | None = None,
        type: str | None = None,
        config: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
        version: str | None = None,
        comment: str | None = None,
        stage: bool = False,
    ) -> Any:
        """Edits the artifact's metadata and saves it."""
        raise NotImplementedError

    @abstractmethod
    def commit(
        self: Self,
        version: str | None = None,
        comment: str | None = None,
    ) -> Any:
        """Commits the staged changes to the artifact."""
        raise NotImplementedError

    @abstractmethod
    def discard(self: Self) -> Any:
        """Discards all staged changes for an artifact."""
        raise NotImplementedError

    @overload
    @abstractmethod
    def cat(
        self: Self,
        path: list[str],
        recursive: bool = False,
        on_error: OnError = "raise",
    ) -> Any: ...

    @overload
    @abstractmethod
    def cat(
        self: Self, path: str, recursive: bool = False, on_error: OnError = "raise"
    ) -> Any: ...

    @abstractmethod
    def cat(
        self: Self,
        path: str | list[str],
        recursive: bool = False,
        on_error: OnError = "raise",
    ) -> Any:
        """Get file(s) content as string(s)"""
        raise NotImplementedError

    @abstractmethod
    def open(
        self: Self,
        urlpath: str,
        mode: str = "rb",
        **kwargs: Any,
    ) -> Any:
        """Open a file for reading or writing"""
        raise NotImplementedError

    @abstractmethod
    def copy(
        self: Self,
        path1: str,
        path2: str,
        recursive: bool = False,
        maxdepth: int | None = None,
        on_error: OnError | None = "raise",
        **kwargs: dict[str, Any],
    ) -> Any:
        """Copy file(s) from path1 to path2 within the artifact"""
        raise NotImplementedError

    @abstractmethod
    def get(
        self: Self,
        rpath: str | list[str],
        lpath: str | list[str],
        recursive: bool = False,
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        **kwargs: Any,
    ) -> Any:
        """Copy file(s) from remote (artifact) to local filesystem"""
        raise NotImplementedError

    @abstractmethod
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
    ) -> Any:
        """Copy file(s) from local filesystem to remote (artifact)"""
        raise NotImplementedError

    @abstractmethod
    def cp(
        self: Self,
        path1: str,
        path2: str,
        on_error: OnError | None = None,
        **kwargs: Any,
    ) -> Any:
        """Alias for copy method"""
        raise NotImplementedError

    @abstractmethod
    def rm(
        self: Self,
        path: str,
        recursive: bool = False,
        maxdepth: int | None = None,
    ) -> Any:
        """Remove file or directory"""
        raise NotImplementedError

    @abstractmethod
    def created(self: Self, path: str) -> Any:
        """Get the creation time of a file"""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self: Self, path: str, recursive: bool = False, maxdepth: int | None = None
    ) -> Any:
        """Delete a file or directory from the artifact"""
        raise NotImplementedError

    @abstractmethod
    def exists(self: Self, path: str, **kwargs: Any) -> Any:
        """Check if a file or directory exists"""
        raise NotImplementedError

    @overload
    @abstractmethod
    def ls(
        self: Self,
        path: str,
        detail: Literal[False],
        **kwargs: Any,
    ) -> Any: ...

    @overload
    @abstractmethod
    def ls(
        self: Self,
        path: str,
        detail: None | Literal[True] = True,
        **kwargs: Any,
    ) -> Any: ...

    @abstractmethod
    def ls(
        self: Self,
        path: str,
        detail: None | bool = True,
        **kwargs: Any,
    ) -> Any:
        """List files and directories in a directory"""
        raise NotImplementedError

    @abstractmethod
    def info(self: Self, path: str, **kwargs: Any) -> Any:
        """Get information about a file or directory"""
        raise NotImplementedError

    @abstractmethod
    def isdir(self: Self, path: str) -> Any:
        """Check if a path is a directory"""
        raise NotImplementedError

    @abstractmethod
    def isfile(self: Self, path: str) -> Any:
        """Check if a path is a file"""
        raise NotImplementedError

    @abstractmethod
    def listdir(self: Self, path: str, **kwargs: Any) -> Any:
        """List files in a directory"""
        raise NotImplementedError

    @overload
    @abstractmethod
    def find(
        self: Self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        *,
        detail: Literal[True],
        **kwargs: dict[str, Any],
    ) -> Any: ...

    @overload
    @abstractmethod
    def find(
        self: Self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: Literal[False] = False,
        **kwargs: dict[str, Any],
    ) -> Any: ...

    @abstractmethod
    def find(
        self: Self,
        path: str,
        maxdepth: int | None = None,
        withdirs: bool = False,
        detail: bool = False,
        **kwargs: dict[str, Any],
    ) -> Any:
        """Find all files (and optional directories) under a path"""
        raise NotImplementedError

    @abstractmethod
    def mkdir(
        self: Self,
        path: str,
        create_parents: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Create a directory"""
        raise NotImplementedError

    @abstractmethod
    def makedirs(
        self: Self,
        path: str,
        exist_ok: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Create a directory and any parent directories"""
        raise NotImplementedError

    @abstractmethod
    def rm_file(self: Self, path: str) -> Any:
        """Remove a file"""
        raise NotImplementedError

    @abstractmethod
    def rmdir(self: Self, path: str) -> Any:
        """Remove an empty directory"""
        raise NotImplementedError

    @abstractmethod
    def head(self: Self, path: str, size: int = 1024) -> Any:
        """Get the first bytes of a file"""
        raise NotImplementedError

    @abstractmethod
    def size(self: Self, path: str) -> Any:
        """Get the size of a file in bytes"""
        raise NotImplementedError

    @abstractmethod
    def sizes(self: Self, paths: list[str]) -> Any:
        """Get the size of multiple files"""
        raise NotImplementedError

    @abstractmethod
    def touch(self: Self, path: str, truncate: bool = True, **kwargs: Any) -> Any:
        """Create an empty file or update the timestamp of an existing file"""
        raise NotImplementedError
