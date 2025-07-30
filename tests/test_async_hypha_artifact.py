"""
Integration tests for the AsyncHyphaArtifact module.

This module contains integration tests for the AsyncHyphaArtifact class,
testing real async file operations such as creation, reading, copying, and deletion
against an actual Hypha artifact service.
"""

import os
from pathlib import Path
from typing import Any
import pytest
import pytest_asyncio
from conftest import ArtifactTestMixin
from hypha_artifact import AsyncHyphaArtifact


@pytest_asyncio.fixture(scope="function", name="async_artifact")
async def get_async_artifact(
    artifact_name: str, artifact_setup_teardown: tuple[str, str]
) -> Any:
    """Create a test artifact with a real async connection to Hypha."""
    token, workspace = artifact_setup_teardown
    artifact = AsyncHyphaArtifact(artifact_name, workspace, token)
    yield artifact
    await artifact.aclose()


class TestAsyncHyphaArtifactIntegration(ArtifactTestMixin):
    """Integration test suite for the AsyncHyphaArtifact class."""

    @pytest.mark.asyncio
    async def test_artifact_initialization(
        self, async_artifact: AsyncHyphaArtifact, artifact_name: str
    ) -> None:
        """Test that the artifact is initialized correctly with real credentials."""
        self._check_artifact_initialization(async_artifact, artifact_name)

    @pytest.mark.asyncio
    async def test_create_file(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Test creating a file in the artifact using real async operations."""
        test_file_path = "async_test_file.txt"

        # Create a test file
        async with async_artifact:
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            # Verify the file was created
            files = await async_artifact.ls("/")
            file_names = [f.get("name") for f in files]
            assert (
                test_file_path in file_names
            ), f"Created file {test_file_path} not found in {file_names}"

    @pytest.mark.asyncio
    async def test_list_files(self, async_artifact: AsyncHyphaArtifact) -> None:
        """Test listing files in the artifact using real async operations."""
        async with async_artifact:
            # First, list files with detail=True (default)
            files = await async_artifact.ls("/")
            self._validate_file_listing(files)
            print(f"Files in artifact: {files}")

            # Test listing with detail=False
            file_names = await async_artifact.ls("/", detail=False)
            self._validate_file_listing(file_names)

    @pytest.mark.asyncio
    async def test_read_file_content(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Test reading content from a file in the artifact using real async operations."""
        test_file_path = "async_test_file.txt"

        async with async_artifact:
            # Ensure the test file exists (create if needed)
            if not await async_artifact.exists(test_file_path):
                await async_artifact.edit(stage=True)
                async with async_artifact.open(test_file_path, "w") as f:
                    await f.write(test_content)
                await async_artifact.commit()

            # Read the file content
            content = await async_artifact.cat(test_file_path)
            self._validate_file_content(content, test_content)

    @pytest.mark.asyncio
    async def test_copy_file(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Test copying a file within the artifact using real async operations."""
        source_path = "async_source_file.txt"
        copy_path = "async_copy_of_source_file.txt"

        async with async_artifact:
            # Create a source file if it doesn't exist
            if not await async_artifact.exists(source_path):
                await async_artifact.edit(stage=True)
                async with async_artifact.open(source_path, "w") as f:
                    await f.write(test_content)
                await async_artifact.commit()

            assert await async_artifact.exists(
                source_path
            ), f"Source file {source_path} should exist before copying"

            # Copy the file
            await async_artifact.edit(stage=True)
            await async_artifact.copy(source_path, copy_path)
            await async_artifact.commit()
            await self._async_validate_copy_operation(
                async_artifact, source_path, copy_path, test_content
            )

    @pytest.mark.asyncio
    async def test_file_existence(self, async_artifact: AsyncHyphaArtifact) -> None:
        """Test checking if files exist in the artifact using real async operations."""
        async with async_artifact:
            # Create a test file to check existence
            test_file_path = "async_existence_test.txt"
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write("Testing file existence")
            await async_artifact.commit()

            # Test for existing file
            await self._async_validate_file_existence(
                async_artifact, test_file_path, True
            )

            # Test for non-existent file
            non_existent_path = "this_async_file_does_not_exist.txt"
            await self._async_validate_file_existence(
                async_artifact, non_existent_path, False
            )

    @pytest.mark.asyncio
    async def test_remove_file(self, async_artifact: AsyncHyphaArtifact) -> None:
        """Test removing a file from the artifact using real async operations."""
        async with async_artifact:
            # Create a file to be removed
            removal_test_file = "async_file_to_remove.txt"

            # Ensure the file exists first
            await async_artifact.edit(stage=True)
            async with async_artifact.open(removal_test_file, "w") as f:
                await f.write("This file will be removed")
            await async_artifact.commit()

            # Verify file exists before removal
            await self._async_validate_file_existence(
                async_artifact, removal_test_file, True
            )

            # Remove the file
            await async_artifact.edit(stage=True)
            await async_artifact.rm(removal_test_file)
            await async_artifact.commit()

            # Verify file no longer exists
            await self._async_validate_file_existence(
                async_artifact, removal_test_file, False
            )

    @pytest.mark.asyncio
    async def test_workflow(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Integration test for a complete async file workflow: create, read, copy, remove."""
        async with async_artifact:
            # File paths for testing
            original_file = "async_workflow_test.txt"
            copied_file = "async_workflow_test_copy.txt"

            # Step 1: Create file
            await async_artifact.edit(stage=True)
            async with async_artifact.open(original_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            # Step 2: Verify file exists and content is correct
            assert await async_artifact.exists(original_file)
            content = await async_artifact.cat(original_file)
            self._validate_file_content(content, test_content)

            # Step 3: Copy file
            await async_artifact.edit(stage=True)
            await async_artifact.copy(original_file, copied_file)
            await async_artifact.commit()
            assert await async_artifact.exists(copied_file)

            # Step 4: Remove copied file
            await async_artifact.edit(stage=True)
            await async_artifact.rm(copied_file)
            await async_artifact.commit()
            await self._async_validate_file_existence(
                async_artifact, copied_file, False
            )
            assert await async_artifact.exists(original_file)

    @pytest.mark.asyncio
    async def test_partial_file_read(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Test reading only part of a file using the size parameter in async read."""
        test_file_path = "async_partial_read_test.txt"

        async with async_artifact:
            # Create a test file
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            # Read only the first 10 bytes of the file
            async with async_artifact.open(test_file_path, "r") as f:
                partial_content = await f.read(10)

            # Verify the partial content matches the expected first 10 bytes
            expected_content = test_content[:10]
            self._validate_file_content(partial_content, expected_content)

    @pytest.mark.asyncio
    async def test_context_manager(
        self, async_artifact: AsyncHyphaArtifact, test_content: str
    ) -> None:
        """Test that the async context manager works correctly."""
        test_file_path = "async_context_test.txt"

        # Test that we can use the artifact within an async context
        async with AsyncHyphaArtifact(
            async_artifact.artifact_alias,
            async_artifact.workspace,
            async_artifact.token,
        ) as ctx_artifact:
            await ctx_artifact.edit(stage=True)
            async with ctx_artifact.open(test_file_path, "w") as f:
                await f.write(test_content)
            await ctx_artifact.commit()

            # Verify the file was created
            assert await ctx_artifact.exists(test_file_path)
            content = await ctx_artifact.cat(test_file_path)
            self._validate_file_content(content, test_content)

    # Async helper methods for validation
    async def _async_validate_file_existence(
        self, artifact: Any, file_path: str, should_exist: bool
    ) -> None:
        """Helper to validate file existence asynchronously."""
        exists = await artifact.exists(file_path)
        if should_exist:
            assert exists is True, f"File {file_path} should exist"
        else:
            assert exists is False, f"File {file_path} should not exist"

    async def _async_validate_copy_operation(
        self, artifact: Any, source_path: str, copy_path: str, expected_content: str
    ) -> None:
        """Validate that copy operation worked correctly asynchronously."""
        # Verify both files exist
        assert await artifact.exists(
            source_path
        ), f"Source file {source_path} should exist after copying"
        assert await artifact.exists(
            copy_path
        ), f"Copied file {copy_path} should exist after copying"

        # Verify content is the same
        source_content = await artifact.cat(source_path)
        copy_content = await artifact.cat(copy_path)
        assert (
            source_content == copy_content == expected_content
        ), "Content in source and copied file should match expected content"

    @pytest.mark.asyncio
    async def test_get_file(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying a file from remote (artifact) to local filesystem."""

        remote_file = "async_get_test_file.txt"
        local_file = tmp_path / "local_get_test_file.txt"

        async with async_artifact:
            # Create a test file in the artifact
            await async_artifact.edit(stage=True)
            async with async_artifact.open(remote_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            # Copy from remote to local
            await async_artifact.get(remote_file, str(local_file))

            # Verify local file exists and has correct content
            assert local_file.exists(), f"Local file {local_file} should exist"
            with open(local_file, "r", encoding="utf-8") as f:
                local_content = f.read()
            self._validate_file_content(local_content, test_content)

    @pytest.mark.asyncio
    async def test_put_file(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying a file from local filesystem to remote (artifact)."""

        local_file = tmp_path / "local_put_test_file.txt"
        remote_file = "async_put_test_file.txt"

        # Create a test file locally
        with open(local_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        async with async_artifact:
            # Copy from local to remote
            await async_artifact.edit(stage=True)
            await async_artifact.put(str(local_file), remote_file)
            await async_artifact.commit()

            # Verify remote file exists and has correct content
            assert await async_artifact.exists(
                remote_file
            ), f"Remote file {remote_file} should exist"
            remote_content = await async_artifact.cat(remote_file)
            self._validate_file_content(remote_content, test_content)

    @pytest.mark.asyncio
    async def test_get_directory_recursive(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying a directory recursively from remote to local."""

        remote_dir = "async_get_dir"
        remote_file1 = f"{remote_dir}/file1.txt"
        remote_file2 = f"{remote_dir}/subdir/file2.txt"
        local_dir = tmp_path / "local_get_dir"

        async with async_artifact:
            # Create test files in the artifact
            await async_artifact.edit(stage=True)
            async with async_artifact.open(remote_file1, "w") as f:
                await f.write(test_content + "_1")
            async with async_artifact.open(remote_file2, "w") as f:
                await f.write(test_content + "_2")
            await async_artifact.commit()

            # Copy directory recursively from remote to local
            await async_artifact.get(remote_dir, str(local_dir), recursive=True)

            # Verify local files exist and have correct content
            local_file1 = local_dir / "file1.txt"
            local_file2 = local_dir / "subdir" / "file2.txt"

            assert local_file1.exists(), f"Local file {local_file1} should exist"
            assert local_file2.exists(), f"Local file {local_file2} should exist"

            with open(local_file1, "r", encoding="utf-8") as f:
                content1 = f.read()
            with open(local_file2, "r", encoding="utf-8") as f:
                content2 = f.read()

            self._validate_file_content(content1, test_content + "_1")
            self._validate_file_content(content2, test_content + "_2")

    @pytest.mark.asyncio
    async def test_put_directory_recursive(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying a directory recursively from local to remote."""

        local_dir = tmp_path / "local_put_dir"
        local_subdir = local_dir / "subdir"
        local_file1 = local_dir / "file1.txt"
        local_file2 = local_subdir / "file2.txt"
        remote_dir = "async_put_dir"

        # Create test directory structure locally
        local_subdir.mkdir(parents=True, exist_ok=True)
        with open(local_file1, "w", encoding="utf-8") as f:
            f.write(test_content + "_1")
        with open(local_file2, "w", encoding="utf-8") as f:
            f.write(test_content + "_2")

        async with async_artifact:
            # Copy directory recursively from local to remote
            await async_artifact.edit(stage=True)
            await async_artifact.put(str(local_dir), remote_dir, recursive=True)
            await async_artifact.commit()

            # Verify remote files exist and have correct content
            remote_file1 = f"{remote_dir}/file1.txt"
            remote_file2 = f"{remote_dir}/subdir/file2.txt"

            assert await async_artifact.exists(
                remote_file1
            ), f"Remote file {remote_file1} should exist"
            assert await async_artifact.exists(
                remote_file2
            ), f"Remote file {remote_file2} should exist"

            content1 = await async_artifact.cat(remote_file1)
            content2 = await async_artifact.cat(remote_file2)

            self._validate_file_content(content1, test_content + "_1")
            self._validate_file_content(content2, test_content + "_2")

    @pytest.mark.asyncio
    async def test_get_multiple_files(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying multiple files from remote to local using lists."""
        remote_files = ["async_get_multi1.txt", "async_get_multi2.txt"]
        local_files = [
            str(tmp_path / "local_get_multi1.txt"),
            str(tmp_path / "local_get_multi2.txt"),
        ]

        async with async_artifact:
            # Create test files in the artifact
            await async_artifact.edit(stage=True)
            for i, remote_file in enumerate(remote_files):
                async with async_artifact.open(remote_file, "w") as f:
                    await f.write(test_content + f"_{i+1}")
            await async_artifact.commit()

            # Copy multiple files from remote to local
            await async_artifact.get(remote_files, local_files)

            # Verify local files exist and have correct content
            for i, local_file in enumerate(local_files):
                assert os.path.exists(
                    local_file
                ), f"Local file {local_file} should exist"
                with open(local_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._validate_file_content(content, test_content + f"_{i+1}")

    @pytest.mark.asyncio
    async def test_put_multiple_files(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test copying multiple files from local to remote using lists."""
        local_files = [
            str(tmp_path / "local_put_multi1.txt"),
            str(tmp_path / "local_put_multi2.txt"),
        ]
        remote_files = ["async_put_multi1.txt", "async_put_multi2.txt"]

        # Create test files locally
        for i, local_file in enumerate(local_files):
            with open(local_file, "w", encoding="utf-8") as f:
                f.write(test_content + f"_{i+1}")

        async with async_artifact:
            # Copy multiple files from local to remote
            await async_artifact.edit(stage=True)
            await async_artifact.put(local_files, remote_files)
            await async_artifact.commit()

            # Verify remote files exist and have correct content
            for i, remote_file in enumerate(remote_files):
                assert await async_artifact.exists(
                    remote_file
                ), f"Remote file {remote_file} should exist"
                content = await async_artifact.cat(remote_file)
                self._validate_file_content(content, test_content + f"_{i+1}")

    @pytest.mark.asyncio
    async def test_progress_callback(
        self, async_artifact: AsyncHyphaArtifact, test_content: str, tmp_path: Path
    ) -> None:
        """Test that progress callback is called during get and put operations."""

        # Track callback calls
        callback_calls: list[dict[str, Any]] = []

        def progress_callback(info: dict[str, Any]):
            callback_calls.append(info)

        test_file = "async_progress_test.txt"
        local_file = str(tmp_path / "local_progress_test.txt")

        async with async_artifact:
            # Create a test file in the artifact
            await async_artifact.edit(stage=True)
            async with async_artifact.open(test_file, "w") as f:
                await f.write(test_content)
            await async_artifact.commit()

            # Test get with progress callback
            await async_artifact.get(
                test_file, local_file, progress_callback=progress_callback
            )

            # Verify callback was called
            assert (
                len(callback_calls) > 0
            ), "Progress callback should be called during get operation"

            # Check that we have info and success messages
            message_types = [call.get("type") for call in callback_calls]
            assert "info" in message_types, "Should have info messages"
            assert "success" in message_types, "Should have success messages"

            # Verify the file was downloaded
            assert os.path.exists(local_file), f"Local file {local_file} should exist"

            # Test put with progress callback (upload the file back with a different name)
            callback_calls.clear()
            test_file2 = "async_progress_test2.txt"

            await async_artifact.edit(stage=True)
            await async_artifact.put(
                local_file, test_file2, progress_callback=progress_callback
            )
            await async_artifact.commit()

            # Verify callback was called for put operation
            assert (
                len(callback_calls) > 0
            ), "Progress callback should be called during put operation"

            # Check that we have info and success messages
            message_types = [call.get("type") for call in callback_calls]
            assert "info" in message_types, "Should have info messages"
            assert "success" in message_types, "Should have success messages"

            # Verify the file was uploaded
            assert await async_artifact.exists(
                test_file2
            ), f"Remote file {test_file2} should exist"
