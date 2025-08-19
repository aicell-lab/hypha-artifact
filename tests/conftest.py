"""Shared test fixtures and utilities for HyphaArtifact tests.

This module contains common fixtures and utility functions used by both
sync and async test suites to avoid code duplication.
"""

# TODO @hugokallander: For all tests, clean up artifacts afterward

import asyncio
import logging
import os
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from dotenv import load_dotenv
from hypha_rpc import connect_to_server

from hypha_artifact import AsyncHyphaArtifact

# Load environment variables from .env file
load_dotenv()

# Skip all tests if no token is available
pytestmark = pytest.mark.skipif(
    os.getenv("HYPHA_TOKEN") is None,
    reason="HYPHA_TOKEN environment variable not set",
)


@pytest.fixture(scope="module", name="artifact_name")
def get_artifact_name() -> str:
    """Generate a unique artifact name for testing."""
    return f"test_artifact_{uuid.uuid4().hex[:8]}"


@pytest.fixture(name="test_content")
def get_test_content() -> str:
    """Provide test file content for testing."""
    return "This is a test file content for integration testing"


async def get_artifact_manager(token: str) -> tuple[Any, Any]:
    """Get the artifact manager and API client.

    Args:
        token (str): The personal access token.

    Returns:
        tuple[Any, Any]: The artifact manager and API client.

    """
    api = await connect_to_server(
        {
            "name": "artifact-client",
            "server_url": "https://hypha.aicell.io",
            "token": token,
        },
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

    logging.info(f"============Creating artifact: {artifact_id}============")
    await artifact_manager.create(
        alias=artifact_id,
        type="generic",
        manifest=manifest,
        config={"permissions": {"*": "rw+", "@": "rw+"}},
    )
    logging.info(f"============Created artifact: {artifact_id}============")

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
    logging.info(f"============Deleting artifact: {artifact_id}============")
    await artifact_manager.delete(artifact_id)
    logging.info(f"============Deleted artifact: {artifact_id}============")

    # Disconnect from the server
    await api.disconnect()


def run_func_sync(
    artifact_id: str,
    token: str,
    func: Callable[[str, str], Any],
) -> None:
    """Synchronous wrapper for async functions"""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(func(artifact_id, token))
    finally:
        loop.close()


@pytest.fixture(scope="module", name="credentials")
def get_credentials() -> tuple[str, str]:
    """Get test credentials."""
    token = os.getenv("HYPHA_TOKEN")
    workspace = os.getenv("HYPHA_WORKSPACE")

    if not token:
        pytest.skip("HYPHA_TOKEN environment variable not set")
    if not workspace:
        pytest.skip("HYPHA_WORKSPACE environment variable not set")

    return token, workspace


@pytest.fixture(scope="module", name="artifact_setup_teardown")
def get_artifact_setup_teardown(artifact_name: str, credentials: tuple[str, str]):
    """Setup and teardown artifact for testing."""
    token, workspace = credentials

    # Setup
    run_func_sync(artifact_name, token, create_artifact)

    yield token, workspace

    # Teardown
    run_func_sync(artifact_name, token, delete_artifact)


class ArtifactTestMixin:
    """Mixin class containing common test methods for both sync and async artifacts."""

    def _check_artifact_initialization(
        self,
        artifact: AsyncHyphaArtifact,
        artifact_name: str,
    ) -> None:
        """Test that the artifact is initialized correctly with real credentials."""
        assert artifact.artifact_alias == artifact_name
        assert artifact.token is not None
        assert artifact.workspace is not None
        assert artifact.artifact_url is not None

    def _validate_file_listing(self, files: list[Any]) -> None:
        """Validate file listing format."""
        assert isinstance(files, list)
        if files:
            # Check for proper file attributes if detail=True
            if isinstance(files[0], dict):
                assert (
                    "name" in files[0]
                ), "File listing should include 'name' attribute"
                assert (
                    "size" in files[0]
                ), "File listing should include 'size' attribute"
            else:
                # Check that file_names contains string values
                assert all(
                    isinstance(name, str) for name in files
                ), "File names should be strings"

    def _validate_file_content(
        self,
        content: str | bytes | None,
        expected_content: str | bytes,
    ) -> None:
        """Validate file content matches expected."""
        assert (
            content == expected_content
        ), f"File content doesn't match. Expected: '{expected_content}', Got: '{content}'"

    def _validate_file_existence(
        self,
        artifact: Any,
        file_path: str,
        should_exist: bool,
    ) -> None:
        """Helper to validate file existence."""
        if should_exist:
            assert artifact.exists(file_path) is True, f"File {file_path} should exist"
        else:
            assert (
                artifact.exists(file_path) is False
            ), f"File {file_path} should not exist"

    def _validate_copy_operation(
        self,
        artifact: Any,
        source_path: str,
        copy_path: str,
        expected_content: str,
    ) -> None:
        """Validate that copy operation worked correctly."""
        # Verify both files exist
        assert artifact.exists(
            source_path,
        ), f"Source file {source_path} should exist after copying"
        assert artifact.exists(
            copy_path,
        ), f"Copied file {copy_path} should exist after copying"

        # Verify content is the same
        source_content = artifact.cat(source_path)
        copy_content = artifact.cat(copy_path)
        assert (
            source_content == copy_content == expected_content
        ), "Content in source and copied file should match expected content"
