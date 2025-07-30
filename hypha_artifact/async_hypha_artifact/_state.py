# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Methods for managing the artifact's state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import AsyncHyphaArtifact


async def edit(
    self: "AsyncHyphaArtifact",
    manifest: dict[str, Any] | None = None,
    artifact_type: str | None = None,
    config: dict[str, Any] | None = None,
    secrets: dict[str, str] | None = None,
    version: str | None = None,
    comment: str | None = None,
    stage: bool = False,
) -> None:
    """Edits the artifact's metadata and saves it."""
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


async def commit(
    self: "AsyncHyphaArtifact",
    version: str | None = None,
    comment: str | None = None,
) -> None:
    """Commits the staged changes to the artifact."""
    params: dict[str, str | None] = {
        "version": version,
        "comment": comment,
    }
    await self._remote_post("commit", params)
