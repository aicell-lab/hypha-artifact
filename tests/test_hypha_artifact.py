"""
Integration tests for the HyphaArtifact module.

This module contains integration tests for the HyphaArtifact class,
testing real file operations such as creation, reading, copying, and deletion
against an actual Hypha artifact service.
"""

import os
import uuid
import asyncio
from typing import Any, Callable, Tuple
import pytest
from hypha_rpc import connect_to_server  # type: ignore
from dotenv import load_dotenv
from hypha_artifact import HyphaArtifact

# Load environment variables from .env file
load_dotenv()

# Skip all tests if no token is available
pytestmark = pytest.mark.skipif(
    os.getenv("PERSONAL_TOKEN") is None,
    reason="PERSONAL_TOKEN environment variable not set",
)


@pytest.fixture(scope="module", name="artifact_name")
def get_artifact_name() -> str:
    """Generate a unique artifact name for testing."""
    return f"test_artifact_{uuid.uuid4().hex[:8]}"


async def get_artifact_manager(token: str) -> Tuple[Any, Any]:
    """Get the artifact manager and API client.

    Args:
        token (str): The personal access token.

    Returns:
        Tuple[Any, Any]: The artifact manager and API client.
    """
    api = await connect_to_server(  # type: ignore
        {
            "name": "artifact-client",
            "server_url": "https://hypha.aicell.io",
            "token": token,
        }
    )

    # Get the artifact manager service
    artifact_manager = await api.get_service("public/artifact-manager")  # type: ignore

    return artifact_manager, api  # type: ignore


async def create_artifact(artifact_id: str, token: str) -> None:
    """Create an artifact with the given ID.
    Args:
        artifact_id (str): The ID of the artifact to create.
        token (str): The personal access token.
    """
    artifact_manager, api = await get_artifact_manager(token)

    # Create the artifact
    manifest = {
        "name": artifact_id,
        "description": f"Artifact created programmatically: {artifact_id}",
    }

    print(f"============Creating artifact: {artifact_id}============")
    await artifact_manager.create(
        alias=artifact_id,
        type="generic",
        manifest=manifest,
        config={"permissions": {"*": "rw+", "@": "rw+"}},
    )
    print(f"============Created artifact: {artifact_id}============")

    # Disconnect from the server
    await api.disconnect()


async def delete_artifact(artifact_id: str, token: str) -> None:
    """Delete an artifact.

    Args:
        artifact_id (str): The ID of the artifact to delete.
        token (str): The personal access token.
    """
    artifact_manager, api = await get_artifact_manager(token)

    # Delete the artifact
    print(f"============Deleting artifact: {artifact_id}============")
    await artifact_manager.delete(artifact_id)
    print(f"============Deleted artifact: {artifact_id}============")

    # Disconnect from the server
    await api.disconnect()


def run_func_sync(
    artifact_id: str, token: str, func: Callable[[str, str], Any]
) -> None:
    """Synchronous wrapper for async functions"""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(func(artifact_id, token))
    finally:
        loop.close()


@pytest.fixture(scope="module", name="artifact")
def get_artifact(artifact_name: str) -> Any:
    """Create a test artifact with a real connection to Hypha."""

    personal_token = os.getenv("PERSONAL_TOKEN")
    workspace = os.getenv("PERSONAL_WORKSPACE")

    if not personal_token:
        pytest.skip("PERSONAL_TOKEN environment variable not set")
    if not workspace:
        pytest.skip("PERSONAL_WORKSPACE environment variable not set")

    run_func_sync(artifact_name, personal_token, create_artifact)
    _artifact = HyphaArtifact(artifact_name, workspace, personal_token)
    yield _artifact
    run_func_sync(artifact_name, personal_token, delete_artifact)


@pytest.fixture(name="test_content")
def get_test_content() -> str:
    """Provide test file content for testing."""
    return "This is a test file content for integration testing"


class TestHyphaArtifactIntegration:
    """Integration test suite for the HyphaArtifact class."""

    def test_artifact_initialization(self, artifact: Any, artifact_name: str) -> None:
        """Test that the artifact is initialized correctly with real credentials."""
        assert artifact.artifact_alias == artifact_name
        assert artifact.token is not None
        assert artifact.workspace_id is not None
        assert artifact.artifact_url is not None

    def test_create_file(self, artifact: Any, test_content: str) -> None:
        """Test creating a file in the artifact using real operations."""
        test_file_path = "test_file.txt"

        # Create a test file
        with artifact.open(test_file_path, "w") as f:
            f.write(test_content)

        # Verify the file was created
        files = artifact.ls("/")
        file_names = [f.get("name") for f in files]
        assert (
            test_file_path in file_names
        ), f"Created file {test_file_path} not found in {file_names}"

    def test_list_files(self, artifact: Any) -> None:
        """Test listing files in the artifact using real operations."""
        # First, list files with detail=True (default)
        files = artifact.ls("/")

        # Verify we got a list with file details
        assert isinstance(files, list)
        if files:
            assert "name" in files[0], "File listing should include 'name' attribute"
            assert "size" in files[0], "File listing should include 'size' attribute"

        # Test listing with detail=False
        file_names: list[str] = artifact.ls("/", detail=False)
        assert isinstance(file_names, list)
        if files:
            # Check that file_names contains string values, not dictionaries
            assert all(
                isinstance(name, str) for name in file_names
            ), "File names should be strings"

    def test_read_file_content(self, artifact: Any, test_content: str) -> None:
        """Test reading content from a file in the artifact using real operations."""
        test_file_path = "test_file.txt"

        # Ensure the test file exists (create if needed)
        if not artifact.exists(test_file_path):
            with artifact.open(test_file_path, "w") as f:
                f.write(test_content)

        # Read the file content
        content = artifact.cat(test_file_path)

        # Verify the content matches
        assert (
            content == test_content
        ), f"File content doesn't match. Expected: '{test_content}', Got: '{content}'"

    def test_copy_file(self, artifact: Any, test_content: str) -> None:
        """Test copying a file within the artifact using real operations."""
        source_path = "source_file.txt"
        copy_path = "copy_of_source_file.txt"

        # Create a source file if it doesn't exist
        if not artifact.exists(source_path):
            with artifact.open(source_path, "w") as f:
                f.write(test_content)

        assert artifact.exists(
            source_path
        ), f"Source file {source_path} should exist before copying"

        # Copy the file
        artifact.copy(source_path, copy_path)

        # Verify both files exist
        assert artifact.exists(
            source_path
        ), f"Source file {source_path} should exist after copying"
        assert artifact.exists(
            copy_path
        ), f"Copied file {copy_path} should exist after copying"

        # Verify content is the same
        source_content = artifact.cat(source_path)
        copy_content = artifact.cat(copy_path)
        assert (
            source_content == copy_content
        ), "Content in source and copied file should match"

    def test_file_existence(self, artifact: Any) -> None:
        """Test checking if files exist in the artifact using real operations."""
        # Create a test file to check existence
        test_file_path = "existence_test.txt"
        with artifact.open(test_file_path, "w") as f:
            f.write("Testing file existence")

        # Test for existing file
        assert (
            artifact.exists(test_file_path) is True
        ), f"File {test_file_path} should exist"

        # Test for non-existent file
        non_existent_path = "this_file_does_not_exist.txt"
        assert (
            artifact.exists(non_existent_path) is False
        ), f"File {non_existent_path} should not exist"

    def test_remove_file(self, artifact: Any) -> None:
        """Test removing a file from the artifact using real operations."""
        # Create a file to be removed
        removal_test_file = "file_to_remove.txt"

        # Ensure the file exists first
        with artifact.open(removal_test_file, "w") as f:
            f.write("This file will be removed")

        # Verify file exists before removal
        assert artifact.exists(
            removal_test_file
        ), f"File {removal_test_file} should exist before removal"

        # Remove the file
        artifact.rm(removal_test_file)

        # Verify file no longer exists
        assert not artifact.exists(
            removal_test_file
        ), f"File {removal_test_file} should no longer exist after removal"

    def test_workflow(self, artifact: Any, test_content: str) -> None:
        """Integration test for a complete file workflow: create, read, copy, remove."""
        # File paths for testing
        original_file = "workflow_test.txt"
        copied_file = "workflow_test_copy.txt"

        # Step 1: Create file
        with artifact.open(original_file, "w") as f:
            f.write(test_content)

        # Step 2: Verify file exists and content is correct
        assert artifact.exists(original_file)
        content = artifact.cat(original_file)
        assert content == test_content

        # Step 3: Copy file
        artifact.copy(original_file, copied_file)
        assert artifact.exists(copied_file)

        # Step 4: Remove copied file
        artifact.rm(copied_file)
        assert not artifact.exists(copied_file)
        assert artifact.exists(original_file)

    def test_partial_file_read(self, artifact: Any, test_content: str) -> None:
        """Test reading only part of a file using the size parameter in read."""
        test_file_path = "partial_read_test.txt"

        # Create a test file
        with artifact.open(test_file_path, "w") as f:
            f.write(test_content)

        # Read only the first 10 bytes of the file
        with artifact.open(test_file_path, "r") as f:
            partial_content = f.read(10)

        # Verify the partial content matches the expected first 10 bytes
        expected_content = test_content[:10]
        assert partial_content == expected_content, (
            "Partial content doesn't match."
            f"Expected: '{expected_content}'"
            f"Got: '{partial_content}'"
        )
