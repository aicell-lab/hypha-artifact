"""
Integration tests for the AsyncHyphaArtifact module.

This module contains integration tests for the AsyncHyphaArtifact class,
testing real async file operations such as creation, reading, copying, and deletion
against an actual Hypha artifact service.
"""

from typing import Any
import pytest
import pytest_asyncio
from hypha_artifact import AsyncHyphaArtifact
from conftest import ArtifactTestMixin


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
