"""
Integration tests for artifact state methods and versioned retrievals.

Covers:
- Async create() and delete() called without parameters.
- Versioned reads across v0 and a newer version for common read methods.
"""

from __future__ import annotations

import uuid
import pytest
import pytest_asyncio

from hypha_artifact import AsyncHyphaArtifact

# pylint: disable=protected-access,redefined-outer-name,broad-except


@pytest_asyncio.fixture
async def ephemeral_artifact(credentials: tuple[str, str]):
    """Yield a brand-new AsyncHyphaArtifact with a unique alias for isolated tests."""
    token, workspace = credentials
    alias = f"test-state-{uuid.uuid4().hex[:8]}"
    artifact = AsyncHyphaArtifact(
        alias,
        workspace=workspace,
        token=token,
        server_url="https://hypha.aicell.io",
    )
    try:
        yield artifact
    finally:
        await artifact.aclose()


class TestAsyncStateMethods:
    """Integration tests for Async create() and delete() methods."""

    @pytest.mark.asyncio
    async def test_create_without_params(self, ephemeral_artifact: AsyncHyphaArtifact):
        """Calling create() with no parameters should succeed and allow listing root."""
        await ephemeral_artifact.create()

        # Basic smoke: can list root on a newly created artifact
        files = await ephemeral_artifact.ls("/")
        assert isinstance(files, list)

        # Cleanup for this test
        await ephemeral_artifact.delete()

    @pytest.mark.asyncio
    async def test_delete_without_params(self, ephemeral_artifact: AsyncHyphaArtifact):
        """Delete with no parameters should remove the entire artifact."""
        # Create first so we can delete it
        await ephemeral_artifact.create()

        # Deleting the entire artifact (default behavior)
        await ephemeral_artifact.delete()

        # Subsequent operations against the deleted artifact should fail
        with pytest.raises(Exception):
            await ephemeral_artifact.ls("/")


class TestVersionedRetrievals:
    """Integration tests that verify the version parameter on read methods."""

    @pytest.mark.asyncio
    async def test_version_parameter_across_methods(self, credentials: tuple[str, str]):
        token, workspace = credentials
        alias = f"test-versions-{uuid.uuid4().hex[:8]}"
        artifact = AsyncHyphaArtifact(
            alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        try:
            # 1) Create artifact -> should create v0 (metadata only)
            await artifact.create()

            # 2) Add a file to v0 (stage and commit without version intent -> updates latest v0)
            fname = "verfile.txt"
            content_v0 = "A-version"
            await artifact.edit(stage=True)
            async with artifact.open(fname, "w") as f:
                await f.write(content_v0)
            await artifact.commit(comment="seed v0 contents")

            # Sanity checks on v0
            assert await artifact.exists(fname, version="v0") is True
            cat_v0 = await artifact.cat(fname, version="v0")
            assert cat_v0 == content_v0

            # 3) Create a new version and change the file content
            content_v1 = "B-version"
            await artifact.edit(stage=True, version="new")
            async with artifact.open(fname, "w") as f:
                await f.write(content_v1)
            await artifact.commit(comment="create new version with updated content")

            # Latest should return v1 content; explicit v0 should return old content
            latest_cat = await artifact.cat(fname)
            assert latest_cat == content_v1
            explicit_v0_cat = await artifact.cat(fname, version="v0")
            assert explicit_v0_cat == content_v0

            # ls with version should see the file in both versions
            names_latest = [i["name"] for i in await artifact.ls("/")]
            assert fname in names_latest
            names_v0 = [i["name"] for i in await artifact.ls("/", version="v0")]
            assert fname in names_v0

            # info/size consistency across versions
            info_latest = await artifact.info(fname)
            info_v0 = await artifact.info(fname, version="v0")
            assert info_latest.get("size") == len(content_v1)
            assert info_v0.get("size") == len(content_v0)

            # head should reflect per-version content
            head_latest = await artifact.head(fname, size=2)
            head_v0 = await artifact.head(fname, size=2, version="v0")
            assert head_latest == content_v1[:2].encode()
            assert head_v0 == content_v0[:2].encode()

        finally:
            # Cleanup: remove the whole artifact
            try:
                await artifact.delete()
            except Exception:
                pass
            await artifact.aclose()
