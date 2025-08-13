"""Methods for managing the artifact's state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._utils import get_headers, get_method_url, prepare_params, check_errors
from ._remote_methods import ArtifactMethod

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


async def edit(
    self: "AsyncHyphaArtifact",
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
    params: dict[str, Any] = prepare_params(
        self,
        {
            "manifest": manifest,
            "type": type,
            "config": config,
            "secrets": secrets,
            "version": version,
            "comment": comment,
            "stage": stage,
        },
    )

    url = get_method_url(self, ArtifactMethod.EDIT)

    response = await self.get_client().post(
        url,
        headers=get_headers(self),
        json=params,
    )

    check_errors(response)


async def commit(
    self: "AsyncHyphaArtifact",
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
    params: dict[str, Any] = prepare_params(
        self,
        {
            "version": version,
            "comment": comment,
        },
    )

    response = await self.get_client().post(
        get_method_url(self, ArtifactMethod.COMMIT),
        headers=get_headers(self),
        json=params,
    )

    check_errors(response)


async def discard(
    self: "AsyncHyphaArtifact",
) -> None:
    """Discards all staged changes for an artifact, reverting to the last committed state."""
    params: dict[str, Any] = prepare_params(
        self,
        {
            "artifact_id": f"{self.workspace}/{self.artifact_alias}",
        },
    )

    response = await self.get_client().post(
        get_method_url(self, ArtifactMethod.DISCARD),
        headers=get_headers(self),
        json=params,
    )

    check_errors(response)
