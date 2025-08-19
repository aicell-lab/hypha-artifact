"""Integration tests for artifact state methods and versioned retrievals.

Covers:
- Async create() and delete() called without parameters.
- Versioned reads across v0 and a newer version for common read methods.
"""

from __future__ import annotations

import asyncio
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
        files = await ephemeral_artifact.ls("/", detail=True)
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
            await ephemeral_artifact.ls("/", detail=True)


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
            try:
                await artifact.delete()
            except Exception:
                pass
            await artifact.aclose()


class TestListChildren:
    """Integration tests for listing child artifacts within a collection."""

    @pytest.mark.asyncio
    async def test_list_children_basic_and_ordering(
        self,
        credentials: tuple[str, str],
    ) -> None:
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
            async def _list_children_committed():
                return await coll.list_children(stage=False)

            for _ in range(5):
                res = await _list_children_committed()
                # Normalize and break early if both names present
                cand = (res.get("items") if isinstance(res, dict) else res) or []
                cand_names = {
                    i.get("manifest", {}).get("name")
                    for i in cand
                    if isinstance(i, dict)
                }
                if {"Alpha", "Beta"}.issubset(cand_names):
                    break
                await asyncio.sleep(0.3)

            res = await _list_children_committed()

            # Result may be a list or a dict with items/results; normalize
            if isinstance(res, dict):
                items = (
                    res.get("items")
                    or res.get("results")
                    or res.get("data")
                    or res.get("artifacts")
                    or []
                )
            else:
                items = res

            assert isinstance(items, list)
            names = {
                i.get("manifest", {}).get("name") for i in items if isinstance(i, dict)
            }
            assert {"Alpha", "Beta"}.issubset(names)

            # Ordering by custom JSON field (descending by likes)
            res_ordered = await coll.list_children(
                order_by="manifest.likes>",
                stage=False,
            )
            if isinstance(res_ordered, dict):
                ordered_items = (
                    res_ordered.get("items")
                    or res_ordered.get("results")
                    or res_ordered.get("data")
                    or res_ordered.get("artifacts")
                    or []
                )
            else:
                ordered_items = res_ordered

            # Ensure we have at least the two children and ordering is respected
            ordered_names = [
                i.get("manifest", {}).get("name")
                for i in ordered_items
                if isinstance(i, dict)
            ]
            # Since likes: Alpha=10, Beta=5 and '>' means descending, Alpha should come before Beta
            if set(["Alpha", "Beta"]).issubset(set(ordered_names)):
                alpha_idx = ordered_names.index("Alpha")
                beta_idx = ordered_names.index("Beta")
                assert alpha_idx < beta_idx

        finally:
            # Cleanup: delete parent recursively (children included)
            try:
                await coll.delete(delete_files=True, recursive=True)
            except Exception:
                pass
            await coll.aclose()
            await child1.aclose()
            await child2.aclose()

    @pytest.mark.asyncio
    async def test_list_children_with_keywords_and_filters_and_stage(
        self,
        credentials: tuple[str, str],
    ) -> None:
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
            kw_res = await coll.list_children(keywords=["Gamma"], stage=False)
            kw_items = kw_res.get("items") if isinstance(kw_res, dict) else kw_res
            assert kw_items
            kw_names = {
                i.get("manifest", {}).get("name")
                for i in kw_items
                if isinstance(i, dict)
            }
            assert "Gamma" in kw_names

            # Filters against manifest fields
            flt_res = await coll.list_children(
                filters={"manifest": {"category": "x"}},
                stage=False,
            )
            flt_items = flt_res.get("items") if isinstance(flt_res, dict) else flt_res
            assert flt_items
            flt_names = {
                i.get("manifest", {}).get("name")
                for i in flt_items
                if isinstance(i, dict)
            }
            assert "Gamma" in flt_names
            assert (
                "Delta" not in flt_names
            )  # staged child shouldn't appear without stage=True

            # Stage-only listing should include the staged child
            stage_only = await coll.list_children(stage=True)
            s_items = (
                stage_only.get("items") if isinstance(stage_only, dict) else stage_only
            )
            assert s_items
            s_names = {
                i.get("manifest", {}).get("name")
                for i in s_items
                if isinstance(i, dict)
            }
            assert "Delta" in s_names
            # And the committed one should not be present when stage=True
            assert "Gamma" not in s_names

        finally:
            try:
                await coll.delete(delete_files=True, recursive=True)
            except Exception:
                pass
            await coll.aclose()
            await staged_child.aclose()
            await committed_child.aclose()
