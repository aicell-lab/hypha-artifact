"""Integration tests for artifact state methods and versioned retrievals.

Covers:
- Async create() and delete() called without parameters.
- Versioned reads across v0 and a newer version for common read methods.
"""

from __future__ import annotations

import asyncio
import contextlib
import typing
import uuid

import httpx
import pytest
import pytest_asyncio

from hypha_artifact import AsyncHyphaArtifact

SMALL_NUMBER = 3
MEDIUM_NUMBER = 5
BIG_NUMBER = 10


@pytest_asyncio.fixture
async def ephemeral_artifact(
    credentials: tuple[str, str],
) -> typing.AsyncGenerator[AsyncHyphaArtifact, None]:
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
    async def test_create_without_params(
        self,
        ephemeral_artifact: AsyncHyphaArtifact,
    ) -> None:
        """Calling create() with no parameters should succeed and allow listing root."""
        await ephemeral_artifact.create()

        # Basic smoke: can list root on a newly created artifact
        files = await ephemeral_artifact.ls("/", detail=True)
        assert isinstance(files, list)

        # Cleanup for this test
        await ephemeral_artifact.delete()

    @pytest.mark.asyncio
    async def test_delete_without_params(
        self,
        ephemeral_artifact: AsyncHyphaArtifact,
    ) -> None:
        """Delete with no parameters should remove the entire artifact."""
        # Create first so we can delete it
        await ephemeral_artifact.create()

        # Deleting the entire artifact (default behavior)
        await ephemeral_artifact.delete()

        # Subsequent operations against the deleted artifact should fail
        with pytest.raises(httpx.RequestError):
            await ephemeral_artifact.ls("/", detail=True)


class TestVersionedRetrievals:
    """Integration tests that verify the version parameter on read methods."""

    @pytest.mark.asyncio
    async def test_version_parameter_across_methods(
        self,
        credentials: tuple[str, str],
    ) -> None:
        """Test version parameter across methods."""
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

            # 2) Add a file to v0 (stage and commit without version intent
            # -> updates latest v0)
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
            names_latest = [i["name"] for i in await artifact.ls("/", detail=True)]
            assert fname in names_latest
            names_v0 = [
                i["name"] for i in await artifact.ls("/", detail=True, version="v0")
            ]
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
            with contextlib.suppress(Exception):
                await artifact.delete()
            await artifact.aclose()


class TestListChildren:
    """Integration tests for listing child artifacts within a collection."""

    @pytest.mark.asyncio
    async def test_list_children_basic_and_ordering(
        self,
        credentials: tuple[str, str],
    ) -> None:
        """Test basic listing and ordering of children."""
        token, workspace = credentials

        # Parent collection
        coll_alias = f"test-coll-{uuid.uuid4().hex[:8]}"
        coll = AsyncHyphaArtifact(
            coll_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        # Two committed children under the collection
        child1_alias = f"alpha-{uuid.uuid4().hex[:4]}"
        child2_alias = f"beta-{uuid.uuid4().hex[:4]}"

        child1 = AsyncHyphaArtifact(
            child1_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )
        child2 = AsyncHyphaArtifact(
            child2_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        try:
            # Create the parent collection (committed v0)
            await coll.create(
                type="collection",
                manifest={"name": coll_alias, "collection": []},
            )

            parent_id = f"{workspace}/{coll_alias}"

            # Create two committed children (default create -> committed v0)
            await child1.create(
                parent_id=parent_id,
                manifest={"name": "Alpha", "likes": 10},
            )
            await child2.create(
                parent_id=parent_id,
                manifest={"name": "Beta", "likes": 5},
            )

            # Basic listing
            # Retry a few times in case of eventual consistency
            async def _list_children_committed() -> list[dict[str, typing.Any]]:
                return await coll.list_children(stage=False)

            for _ in range(5):
                res = await _list_children_committed()

                # Normalize and break early if both names present
                cand_names = {i.get("manifest", {}).get("name") for i in res}
                if {"Alpha", "Beta"}.issubset(cand_names):
                    break
                await asyncio.sleep(0.3)

            res = await _list_children_committed()

            assert isinstance(res, list)
            names = {i.get("manifest", {}).get("name") for i in res}
            assert {"Alpha", "Beta"}.issubset(names)

            # Ordering by custom JSON field (descending by likes)
            ordered_children = await coll.list_children(
                order_by="manifest.likes>",
                stage=False,
            )

            encountered_alpha = False
            for child in ordered_children:
                manifest_raw = child.get("manifest")
                assert isinstance(manifest_raw, dict)
                manifest = typing.cast("dict[str, str]", manifest_raw)
                name = manifest.get("name")
                if name == "Alpha":
                    encountered_alpha = True
                elif name == "Beta":
                    break

            if not encountered_alpha:
                pytest.fail("Alpha child not found in ordered listing")

        finally:
            # Cleanup: delete parent recursively (children included)
            with contextlib.suppress(Exception):
                await coll.delete(delete_files=True, recursive=True)
            await coll.aclose()
            await child1.aclose()
            await child2.aclose()

    @pytest.mark.asyncio
    async def test_list_children_with_keywords_and_filters_and_stage(
        self,
        credentials: tuple[str, str],
    ) -> None:
        """Test listing children with keywords, filters and stage parameter."""
        token, workspace = credentials

        coll_alias = f"test-coll-{uuid.uuid4().hex[:8]}"
        staged_child_alias = f"staged-{uuid.uuid4().hex[:4]}"
        committed_child_alias = f"commit-{uuid.uuid4().hex[:4]}"

        coll = AsyncHyphaArtifact(
            coll_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )
        staged_child = AsyncHyphaArtifact(
            staged_child_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )
        committed_child = AsyncHyphaArtifact(
            committed_child_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        try:
            await coll.create(
                type="collection",
                manifest={"name": coll_alias, "collection": []},
            )
            parent_id = f"{workspace}/{coll_alias}"

            # One committed child
            await committed_child.create(
                parent_id=parent_id,
                manifest={"name": "Gamma", "category": "x"},
            )

            # One staged child (do not commit)
            await staged_child.create(
                parent_id=parent_id,
                manifest={"name": "Delta", "category": "y"},
                version="stage",
            )

            # Keywords should match by name
            # Committed-only listing should find Gamma
            kw_items = await coll.list_children(keywords=["Gamma"], stage=False)
            assert kw_items
            kw_names = {
                typing.cast("dict[str, str]", kw_item.get("manifest", {})).get(
                    "name",
                )
                for kw_item in kw_items
            }
            assert "Gamma" in kw_names

            # Filters against manifest fields
            flt_items_raw = await coll.list_children(
                filters={"manifest": {"category": "x"}},
                stage=False,
            )
            flt_items = typing.cast("list[dict[str, typing.Any]]", flt_items_raw)
            assert flt_items
            flt_names = {i.get("manifest", {}).get("name") for i in flt_items}
            assert "Gamma" in flt_names
            assert (
                "Delta" not in flt_names
            )  # staged child shouldn't appear without stage=True

            # Stage-only listing should include the staged child
            stage_only = await coll.list_children(stage=True)
            s_items_raw: object
            if isinstance(stage_only, dict):
                stage_only_dict = typing.cast("dict[str, str]", stage_only)
                s_items_raw = stage_only_dict.get("items")
            else:
                s_items_raw = stage_only
            s_items = typing.cast("list[dict[str, dict[str, object]]]", s_items_raw)
            assert s_items
            s_names = {i.get("manifest", {}).get("name") for i in s_items}
            assert "Delta" in s_names
            # And the committed one should not be present when stage=True
            assert "Gamma" not in s_names

        finally:
            with contextlib.suppress(Exception):
                await coll.delete(delete_files=True, recursive=True)
            await coll.aclose()
            await staged_child.aclose()
            await committed_child.aclose()


class TestListFilesLimit:
    """Integration tests for the limit parameter in the ls method."""

    @pytest.mark.asyncio
    async def test_ls_limit_parameter(
        self,
        credentials: tuple[str, str],
    ) -> None:
        """Test that the limit parameter restricts the number of files."""
        token, workspace = credentials

        # Create a test artifact
        artifact_alias = f"test-limit-{uuid.uuid4().hex[:8]}"
        artifact = AsyncHyphaArtifact(
            artifact_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        try:
            # Create the artifact
            await artifact.create()

            # Create multiple test files (more than the limit we'll test with)
            num_files = 15
            file_names = [f"test_file_{i:02d}.txt" for i in range(num_files)]

            await artifact.edit(stage=True)
            for file_name in file_names:
                async with artifact.open(file_name, "w") as f:
                    await f.write(f"Content for {file_name}")
            await artifact.commit(comment="Add test files for limit testing")

            # Test with limit=5
            limited_files = await artifact.ls("/", limit=MEDIUM_NUMBER, detail=True)
            assert isinstance(limited_files, list)
            assert (
                len(limited_files) <= MEDIUM_NUMBER
            ), f"Expected at most {MEDIUM_NUMBER} files, got {len(limited_files)}"
            # Test with limit=10
            limited_files_10 = await artifact.ls("/", limit=BIG_NUMBER, detail=True)
            assert isinstance(limited_files_10, list)
            assert (
                len(limited_files_10) <= BIG_NUMBER
            ), f"Expected at most {BIG_NUMBER} files, got {len(limited_files_10)}"
            # Test without detail
            limited_names = await artifact.ls("/", limit=MEDIUM_NUMBER, detail=False)
            assert isinstance(limited_names, list)
            assert (
                len(limited_names) <= MEDIUM_NUMBER
            ), f"Expected at most {MEDIUM_NUMBER} file names, got {len(limited_names)}"
            assert all(
                isinstance(name, str) for name in limited_names
            ), "All items should be strings"

            # Test with default limit (should return all files)
            all_files = await artifact.ls("/", detail=True)
            assert isinstance(all_files, list)
            # Should contain all files we created
            assert (
                len(all_files) >= num_files
            ), f"Expected at least {num_files} files, got {len(all_files)}"

            # Verify that the files returned are valid artifact items
            if limited_files:
                first_file = limited_files[0]
                assert "name" in first_file, "File should have a 'name' field"
                assert "type" in first_file, "File should have a 'type' field"
                assert "size" in first_file, "File should have a 'size' field"

        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await artifact.delete(delete_files=True, recursive=True)
            await artifact.aclose()

    @pytest.mark.asyncio
    async def test_ls_limit_with_version(
        self,
        credentials: tuple[str, str],
    ) -> None:
        """Test that the limit parameter works correctly with version parameter."""
        token, workspace = credentials

        artifact_alias = f"test-limit-version-{uuid.uuid4().hex[:8]}"
        artifact = AsyncHyphaArtifact(
            artifact_alias,
            workspace=workspace,
            token=token,
            server_url="https://hypha.aicell.io",
        )

        try:
            # Create the artifact with initial files
            await artifact.create()

            # Add files to v0
            num_files_v0 = 8
            await artifact.edit(stage=True)
            for i in range(num_files_v0):
                async with artifact.open(f"file_v0_{i}.txt", "w") as f:
                    await f.write(f"Content v0 {i}")
            await artifact.commit(comment="Initial files in v0")

            # Test limit on v0
            limited_v0 = await artifact.ls(
                "/",
                limit=SMALL_NUMBER,
                version="v0",
                detail=True,
            )
            assert isinstance(limited_v0, list)
            assert (
                len(limited_v0) <= SMALL_NUMBER
            ), f"Expected at most {SMALL_NUMBER} files from v0, got {len(limited_v0)}"
            # Create a new version with additional files
            await artifact.edit(stage=True, version="new")
            for i in range(5):
                async with artifact.open(f"file_v1_{i}.txt", "w") as f:
                    await f.write(f"Content v1 {i}")
            await artifact.commit(comment="Additional files in new version")

            # Test limit on latest version
            limited_latest = await artifact.ls("/", limit=MEDIUM_NUMBER, detail=True)
            assert isinstance(limited_latest, list)
            assert (
                len(limited_latest) <= MEDIUM_NUMBER
            ), f"Expected max. {MEDIUM_NUMBER} files, got {len(limited_latest)}"
            # Test limit on v0 again to ensure it still returns v0 files only
            limited_v0_again = await artifact.ls(
                "/",
                limit=MEDIUM_NUMBER - 1,
                version="v0",
                detail=False,
            )
            assert isinstance(limited_v0_again, list)
            assert (
                len(limited_v0_again) <= 4  # noqa: PLR2004
            ), f"Expected at most 4 file names from v0, got {len(limited_v0_again)}"

        finally:
            # Cleanup
            with contextlib.suppress(Exception):
                await artifact.delete(delete_files=True, recursive=True)
            await artifact.aclose()
