# ruff: noqa: S101, I001

"""Integration tests for the AsyncHyphaArtifact module.

This module contains integration tests for the AsyncHyphaArtifact class,
covering async file operations like create, read, copy, delete, and directory transfers
against a real Hypha artifact service.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from hypha_artifact import AsyncHyphaArtifact
from tests.conftest import ArtifactTestMixin


logger = logging.getLogger(__name__)


@pytest_asyncio.fixture(scope="function", name="async_artifact")
async def get_async_artifact(
    artifact_name: str,
    artifact_setup_teardown: tuple[str, str],
) -> AsyncIterator[AsyncHyphaArtifact]:
    """Create a test artifact with a real async connection to Hypha."""
    token, workspace = artifact_setup_teardown
    artifact = AsyncHyphaArtifact(
        artifact_name,
        workspace,
        token,
        server_url="https://hypha.aicell.io",
    )
    try:
        yield artifact
    finally:
        await artifact.aclose()


class TestAsyncHyphaArtifactIntegration(ArtifactTestMixin):
    """Integration test suite for the AsyncHyphaArtifact class."""

    @pytest.mark.asyncio
    async def test_artifact_initialization(
        self,
        async_artifact: AsyncHyphaArtifact,
        artifact_name: str,
    ) -> None:
        """Validate artifact is initialized correctly with real credentials."""
        self._check_artifact_initialization(async_artifact, artifact_name)

    @pytest.mark.asyncio
    async def test_create_file(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Create a file and verify it is listed."""
        test_file_path = "async_test_file.txt"

        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            files = await async_artifact.ls("/", detail=True)
            file_names = [f["name"] for f in files]
            assert test_file_path in file_names

    @pytest.mark.asyncio
    async def test_list_files(self, async_artifact: AsyncHyphaArtifact) -> None:
        """List files with and without detail and validate output."""
        async with async_artifact:
            files = await async_artifact.ls("/", detail=True)
            self._validate_file_listing(files)
            logger.info("Files in artifact: %s", files)

            file_names = await async_artifact.ls("/")
            self._validate_file_listing(file_names)

    @pytest.mark.asyncio
    async def test_read_file_content(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Read content from a file and validate it."""
        test_file_path = "async_test_file.txt"

        async with async_artifact:
            if not await async_artifact.exists(test_file_path):
                await async_artifact.edit(stage=True)
                async with async_artifact.open(test_file_path, "w") as f:
                    await f.write(test_content)
                await async_artifact.commit()

            content = await async_artifact.cat(test_file_path)
            self._validate_file_content(content, test_content)

    @pytest.mark.asyncio
    async def test_copy_file(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Copy a file and verify both existence and content."""
        source_path = "async_source_file.txt"
        copy_path = "async_copy_of_source_file.txt"

        async with async_artifact:
            if not await async_artifact.exists(source_path):
                await async_artifact.edit(stage=True)
                async with async_artifact.open(source_path, "w") as f:
                    await f.write(test_content)
                await async_artifact.commit()

            assert await async_artifact.exists(source_path)

            await async_artifact.edit(stage=True)
            await async_artifact.copy(source_path, copy_path)
            await async_artifact.commit()
            await self._async_validate_copy_operation(
                async_artifact,
                source_path,
                copy_path,
                test_content,
            )

    @pytest.mark.asyncio
    async def test_file_existence(self, async_artifact: AsyncHyphaArtifact) -> None:
        """Check both existing and non-existing files."""
        async with async_artifact:
            test_file_path = "async_existence_test.txt"
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write("Testing file existence")
            await async_artifact.commit()

            await self._async_validate_file_existence(
                async_artifact,
                test_file_path,
                should_exist=True,
            )

            non_existent_path = "this_async_file_does_not_exist.txt"
            await self._async_validate_file_existence(
                async_artifact,
                non_existent_path,
                should_exist=False,
            )

    @pytest.mark.asyncio
    async def test_remove_file(self, async_artifact: AsyncHyphaArtifact) -> None:
        """Remove a file and validate it is gone."""
        async with async_artifact:
            removal_test_file = "async_file_to_remove.txt"

            await async_artifact.edit(stage=True)
            async with async_artifact.open(removal_test_file, "w") as f:
                await f.write("This file will be removed")
            await async_artifact.commit()

            await self._async_validate_file_existence(
                async_artifact,
                removal_test_file,
                should_exist=True,
            )

            await async_artifact.edit(stage=True)
            await async_artifact.rm(removal_test_file)
            await async_artifact.commit()

            await self._async_validate_file_existence(
                async_artifact,
                removal_test_file,
                should_exist=False,
            )

    @pytest.mark.asyncio
    async def test_workflow(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Create, read, copy, and remove a file in sequence."""
        async with async_artifact:
            original_file = "async_workflow_test.txt"
            copied_file = "async_workflow_test_copy.txt"

            await async_artifact.edit(stage=True)
            async with async_artifact.open(original_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            assert await async_artifact.exists(original_file)
            content = await async_artifact.cat(original_file)
            self._validate_file_content(content, test_content)

            await async_artifact.edit(stage=True)
            await async_artifact.copy(original_file, copied_file)
            await async_artifact.commit()
            assert await async_artifact.exists(copied_file)

            await async_artifact.edit(stage=True)
            await async_artifact.rm(copied_file)
            await async_artifact.commit()
            await self._async_validate_file_existence(
                async_artifact,
                copied_file,
                should_exist=False,
            )
            assert await async_artifact.exists(original_file)

    @pytest.mark.asyncio
    async def test_partial_file_read(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Read only first 10 bytes and compare to expected."""
        test_file_path = "async_partial_read_test.txt"

        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            async with async_artifact.open(test_file_path, "r") as f:
                partial_content = await f.read(10)

            expected_content = test_content[:10]
            self._validate_file_content(partial_content, expected_content)

    @pytest.mark.asyncio
    async def test_context_manager(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
    ) -> None:
        """Use the artifact within an async context manager."""
        test_file_path = "async_context_test.txt"

        async with AsyncHyphaArtifact(
            async_artifact.artifact_alias,
            async_artifact.workspace,
            async_artifact.token,
            server_url="https://hypha.aicell.io",
        ) as ctx_artifact:
            await ctx_artifact.edit(stage=True)
            async with ctx_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await ctx_artifact.commit()

            assert await ctx_artifact.exists(test_file_path)
            content = await ctx_artifact.cat(test_file_path)
            self._validate_file_content(content, test_content)

    async def _async_validate_file_existence(
        self,
        artifact: AsyncHyphaArtifact,
        file_path: str,
        *,
        should_exist: bool,
    ) -> None:
        """Validate file existence asynchronously."""
        exists = await artifact.exists(file_path)
        if should_exist:
            assert exists is True, f"File {file_path} should exist"
        else:
            assert exists is False, f"File {file_path} should not exist"

    async def _async_validate_copy_operation(
        self,
        artifact: AsyncHyphaArtifact,
        source_path: str,
        copy_path: str,
        expected_content: str,
    ) -> None:
        """Validate copy operation results asynchronously."""
        assert await artifact.exists(
            source_path,
        ), f"Source file {source_path} should exist after copying"
        assert await artifact.exists(
            copy_path,
        ), f"Copied file {copy_path} should exist after copying"

        source_content = await artifact.cat(source_path)
        copy_content = await artifact.cat(copy_path)
        assert (
            source_content == copy_content == expected_content
        ), "Content in source and copied file should match expected content"

    @pytest.mark.asyncio
    async def test_get_file(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy a file from remote (artifact) to local filesystem."""
        remote_file = "async_get_test_file.txt"
        local_file = tmp_path / "local_get_test_file.txt"

        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(remote_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            await async_artifact.get(remote_file, str(local_file))

            assert local_file.exists()
            local_content = await asyncio.to_thread(
                local_file.read_text,
                encoding="utf-8",
            )
            self._validate_file_content(local_content, test_content)

    @pytest.mark.asyncio
    async def test_put_file(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy a file from local filesystem to remote (artifact)."""
        local_file = tmp_path / "local_put_test_file.txt"
        remote_file = "async_put_test_file.txt"

        await asyncio.to_thread(local_file.write_text, test_content, encoding="utf-8")

        async with async_artifact:
            await async_artifact.edit(stage=True)
            await async_artifact.put(str(local_file), remote_file)
            await async_artifact.commit()

            assert await async_artifact.exists(remote_file)
            remote_content = await async_artifact.cat(remote_file)
            self._validate_file_content(remote_content, test_content)

    @pytest.mark.asyncio
    async def test_get_directory_recursive(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy a directory recursively from remote to local."""
        remote_dir = "async_get_dir"
        remote_file1 = f"{remote_dir}/file1.txt"
        remote_file2 = f"{remote_dir}/subdir/file2.txt"
        local_dir = tmp_path / "local_get_dir"

        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(remote_file1, "w") as f:
                await f.write(test_content + "_1")
            async with async_artifact.open(remote_file2, "w") as f:
                await f.write(test_content + "_2")
            await async_artifact.commit()

            await async_artifact.get(remote_dir, str(local_dir), recursive=True)

            local_file1 = local_dir / "file1.txt"
            local_file2 = local_dir / "subdir" / "file2.txt"

            assert local_file1.exists()
            assert local_file2.exists()

            content1 = await asyncio.to_thread(
                local_file1.read_text,
                encoding="utf-8",
            )
            content2 = await asyncio.to_thread(
                local_file2.read_text,
                encoding="utf-8",
            )

            self._validate_file_content(content1, test_content + "_1")
            self._validate_file_content(content2, test_content + "_2")

    @pytest.mark.asyncio
    async def test_put_directory_recursive(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy a directory recursively from local to remote."""
        local_dir = tmp_path / "local_put_dir"
        local_subdir = local_dir / "subdir"
        local_file1 = local_dir / "file1.txt"
        local_file2 = local_subdir / "file2.txt"
        remote_dir = "async_put_dir"

        local_subdir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            local_file1.write_text,
            test_content + "_1",
            encoding="utf-8",
        )
        await asyncio.to_thread(
            local_file2.write_text,
            test_content + "_2",
            encoding="utf-8",
        )

        async with async_artifact:
            await async_artifact.edit(stage=True)
            await async_artifact.put(str(local_dir), remote_dir, recursive=True)
            await async_artifact.commit()

            remote_file1 = f"{remote_dir}/file1.txt"
            remote_file2 = f"{remote_dir}/subdir/file2.txt"

            assert await async_artifact.exists(remote_file1)
            assert await async_artifact.exists(remote_file2)

            content1 = await async_artifact.cat(remote_file1)
            content2 = await async_artifact.cat(remote_file2)

            self._validate_file_content(content1, test_content + "_1")
            self._validate_file_content(content2, test_content + "_2")

    @pytest.mark.asyncio
    async def test_get_multiple_files(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy multiple files from remote to local using lists."""
        remote_files = ["async_get_multi1.txt", "async_get_multi2.txt"]
        local_files = [
            str(tmp_path / "local_get_multi1.txt"),
            str(tmp_path / "local_get_multi2.txt"),
        ]

        async with async_artifact:
            await async_artifact.edit(stage=True)
            for i, remote_file in enumerate(remote_files):
                async with async_artifact.open(remote_file, "w") as f:
                    await f.write(test_content + f"_{i+1}")
            await async_artifact.commit()

            await async_artifact.get(remote_files, local_files)

            for i, local_file in enumerate(local_files):
                path_obj = Path(local_file)
                assert path_obj.exists()
                content = await asyncio.to_thread(
                    path_obj.read_text,
                    encoding="utf-8",
                )
                self._validate_file_content(content, test_content + f"_{i+1}")

    @pytest.mark.asyncio
    async def test_put_multiple_files(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Copy multiple files from local to remote using lists."""
        local_files = [
            str(tmp_path / "local_put_multi1.txt"),
            str(tmp_path / "local_put_multi2.txt"),
        ]
        remote_files = ["async_put_multi1.txt", "async_put_multi2.txt"]

        for i, local_file in enumerate(local_files):
            path_obj = Path(local_file)
            await asyncio.to_thread(
                path_obj.write_text,
                test_content + f"_{i+1}",
                encoding="utf-8",
            )

        async with async_artifact:
            await async_artifact.edit(stage=True)
            await async_artifact.put(local_files, remote_files)
            await async_artifact.commit()

            for i, remote_file in enumerate(remote_files):
                assert await async_artifact.exists(remote_file)
                content = await async_artifact.cat(remote_file)
                self._validate_file_content(content, test_content + f"_{i+1}")

    @pytest.mark.asyncio
    async def test_progress_callback(
        self,
        async_artifact: AsyncHyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Ensure progress callback is called on get and put operations."""
        callback_calls: list[dict[str, object]] = []

        def progress_callback(info: dict[str, object]) -> None:
            callback_calls.append(info)

        test_file = "async_progress_test.txt"
        local_file = str(tmp_path / "local_progress_test.txt")

        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            await async_artifact.get(test_file, local_file, callback=progress_callback)

            assert len(callback_calls) > 0
            message_types = [call.get("type") for call in callback_calls]
            assert "info" in message_types
            assert "success" in message_types

            assert Path(local_file).exists()

            callback_calls.clear()
            test_file2 = "async_progress_test2.txt"

            await async_artifact.edit(stage=True)
            await async_artifact.put(
                local_file,
                test_file2,
                callback=progress_callback,
            )
            await async_artifact.commit()

            assert len(callback_calls) > 0
            message_types = [call.get("type") for call in callback_calls]
            assert "info" in message_types
            assert "success" in message_types

            assert await async_artifact.exists(test_file2)
