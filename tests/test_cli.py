# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Real integration tests for the Hypha Artifact CLI.

These tests use actual Hypha connections and real file operations.
Requires valid credentials in .env file.
"""

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dotenv import find_dotenv, load_dotenv
from httpx import HTTPError

from cli.main import (
    ArtifactCLI,
    get_connection_params,
)

if TYPE_CHECKING:
    from hypha_artifact.classes import MultipartConfig

# Load environment variables
load_dotenv(override=True, dotenv_path=find_dotenv(usecwd=True))


@pytest.fixture(scope="module", name="real_artifact")
def get_artifact(
    artifact_name: str,
    artifact_setup_teardown: tuple[str, str],
) -> object:
    """Create a test artifact with a real connection to Hypha."""
    token, workspace = artifact_setup_teardown
    return ArtifactCLI(
        artifact_name,
        workspace,
        token,
        server_url="https://hypha.aicell.io",
    )


class TestRealEnvironment:
    """Test real environment setup and connection."""

    def test_environment_variables_available(self) -> None:
        """Test that required environment variables are available."""
        server_url = os.getenv("HYPHA_SERVER_URL")
        workspace = os.getenv("HYPHA_WORKSPACE")
        token = os.getenv("HYPHA_TOKEN")

        assert server_url, "HYPHA_SERVER_URL environment variable is required"
        assert workspace, "HYPHA_WORKSPACE environment variable is required"
        assert token, "HYPHA_TOKEN environment variable is required"

    def test_real_connection_params(self) -> None:
        """Test real connection parameter retrieval."""
        connection_params = get_connection_params()

        assert connection_params["HYPHA_SERVER_URL"], "Server URL should be set"
        assert connection_params["HYPHA_WORKSPACE"], "Workspace should be set"
        assert connection_params["HYPHA_TOKEN"], "Token should be set"

    def test_real_artifact_creation(self) -> None:
        """Test real artifact creation."""
        artifact = ArtifactCLI("test-cli-artifact")
        # Check that the artifact was created successfully
        assert hasattr(artifact, "ls")
        assert hasattr(artifact, "put")


class TestRealFileOperations:
    """Test real file operations with actual Hypha connections."""

    def test_real_ls_command(self, real_artifact: ArtifactCLI) -> None:
        """Test real ls command."""
        items = real_artifact.ls("/", detail=True)
        assert isinstance(items, list)

    def test_real_staging_workflow(self, real_artifact: ArtifactCLI) -> None:
        """Test real staging workflow using proper artifact manager API."""
        # Create a test file
        test_content = "This is a test file for API staging workflow\n"

        # Step 1: Put artifact in staging mode
        # Before staging - checking current artifact state...
        with contextlib.suppress(Exception):
            real_artifact.ls("/", detail=True)

        # Clean up any existing staged changes first
        with contextlib.suppress(Exception):
            real_artifact.discard()

        # Putting artifact in staging mode with new version intent...
        real_artifact.edit(
            stage=True,
            version="new",
            comment="Testing proper staging workflow",
        )

        # Step 2: Get presigned URL and upload file
        with real_artifact.open("/api-staging-test.txt", "w") as f:
            f.write(test_content)

        # Step 3: Commit the changes
        real_artifact.commit(comment="Committed API staging test")

        # Step 4: Verify file exists after commit
        assert real_artifact.exists("/api-staging-test.txt")
        content = real_artifact.cat("/api-staging-test.txt")
        assert content == test_content

    def test_real_multipart_upload(self, real_artifact: ArtifactCLI) -> None:
        """Test real multipart upload using proper API workflow."""
        # Create a smaller test file (20 MB) to reduce network load
        file_size = 20 * 1024 * 1024  # 20 MB
        chunk_size = 6 * 1024 * 1024  # 6 MB chunks
        threshold = 2 * 1024 * 1024  # 2MB threshold

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            # Write test data
            chunk = b"M" * (1024 * 1024)  # 1MB chunks
            for _ in range(20):
                f.write(chunk)
            temp_file_path = Path(f.name)

        try:
            # Step 1: Clean up and put artifact in staging mode
            # Clean up any existing staged changes first
            with contextlib.suppress(Exception):
                real_artifact.discard()

            real_artifact.edit(
                stage=True,
                version="new",
                comment="Testing multipart upload",
            )

            multipart_config: MultipartConfig = {
                "enable": True,
                "threshold": threshold,
                "chunk_size": chunk_size,
            }

            real_artifact.put(
                lpath=str(temp_file_path),
                rpath="/multipart-test.bin",
                multipart_config=multipart_config,
            )

            # Step 3: Commit the upload
            real_artifact.commit(comment="Committed multipart upload")

            # Step 4: Verify file exists and has correct size
            assert real_artifact.exists("/multipart-test.bin")
            info = real_artifact.info("/multipart-test.bin")
            assert info["size"] == file_size

        finally:
            # Clean up temp file
            if temp_file_path.exists():
                temp_file_path.unlink()

    def test_real_directory_upload(self, real_artifact: ArtifactCLI) -> None:
        """Test real directory upload using proper API workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test directory structure
            (temp_path / "subdir").mkdir()
            (temp_path / "file1.txt").write_text("Content of file 1")
            (temp_path / "file2.txt").write_text("Content of file 2")
            (temp_path / "subdir" / "file3.txt").write_text("Content of file 3")

            # Step 1: Clean up and put artifact in staging mode
            # Clean up any existing staged changes first
            with contextlib.suppress(Exception):
                real_artifact.discard()

            real_artifact.edit(
                stage=True,
                version="new",
                comment="Testing directory upload",
            )

            real_artifact.put(
                lpath=str(temp_path),
                rpath="/api-test-dir",
                recursive=True,
            )

            # Step 3: Commit the upload
            real_artifact.commit(comment="Committed directory upload")

            # Step 4: Verify directory structure
            assert real_artifact.exists("/api-test-dir")
            assert real_artifact.exists("/api-test-dir/file1.txt")
            assert real_artifact.exists("/api-test-dir/file2.txt")
            assert real_artifact.exists("/api-test-dir/subdir/file3.txt")

            # Verify file contents
            assert real_artifact.cat("/api-test-dir/file1.txt") == "Content of file 1"
            assert (
                real_artifact.cat("/api-test-dir/subdir/file3.txt")
                == "Content of file 3"
            )

    def test_real_file_operations(self, real_artifact: ArtifactCLI) -> None:
        """Test real file operations using proper API workflow."""
        # Create initial test file
        test_content = "Test file for operations\n"

        # Step 1: Clean up and put artifact in staging mode
        # Clean up any existing staged changes first
        with contextlib.suppress(Exception):
            real_artifact.discard()

        real_artifact.edit(stage=True, version="new", comment="Testing file operations")

        with real_artifact.open("/ops-test.txt", "w") as f:
            f.write(test_content)

        # Step 2: Commit the initial upload
        real_artifact.commit(comment="Initial file for operations test")

        # Step 3: Test file operations (these work on committed files)

        # Copy file
        real_artifact.edit(stage=True)
        real_artifact.copy("/ops-test.txt", "/ops-test-copy.txt")
        real_artifact.commit()
        assert real_artifact.exists("/ops-test-copy.txt")

        # Verify copy has same content
        copy_content = real_artifact.cat("/ops-test-copy.txt")
        assert copy_content == test_content

        # Create directory and copy file there
        real_artifact.edit(stage=True)
        real_artifact.mkdir("/ops-test-dir")
        real_artifact.copy("/ops-test.txt", "/ops-test-dir/operations.txt")
        real_artifact.commit()
        assert real_artifact.exists("/ops-test-dir/operations.txt")

        # Remove files
        real_artifact.edit(stage=True)
        real_artifact.rm("/ops-test-copy.txt")
        real_artifact.commit()
        assert not real_artifact.exists("/ops-test-copy.txt")

    def test_real_find_command(self, real_artifact: ArtifactCLI) -> None:
        """Test real find command."""
        files = real_artifact.find("/")
        assert isinstance(files, list)


class TestRealCLICommands:
    """Test real CLI commands with actual subprocess calls."""

    @pytest.fixture
    def cli_env(self) -> dict[str, str]:
        """Get environment variables for CLI testing."""
        env = os.environ.copy()
        # Ensure we have the required environment variables
        env["HYPHA_SERVER_URL"] = os.getenv("HYPHA_SERVER_URL", "")
        env["HYPHA_WORKSPACE"] = os.getenv("HYPHA_WORKSPACE", "")
        env["HYPHA_TOKEN"] = os.getenv("HYPHA_TOKEN", "")
        return env

    def test_real_cli_ls(
        self,
        cli_env: dict[str, str],
        artifact_name: str,
        real_artifact: ArtifactCLI,  # noqa: ARG002
    ) -> None:
        """Test real CLI ls command."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.main",
                f"--artifact-id={artifact_name}",
                "ls",
                "/",
            ],
            env=cli_env,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.returncode == 0, f"CLI ls command failed: {result.stderr}"

    def test_real_cli_staging_workflow(
        self,
        cli_env: dict[str, str],
        artifact_name: str,
        real_artifact: ArtifactCLI,  # noqa: ARG002
    ) -> None:
        """Test real CLI staging workflow using edit and commit commands."""
        # Create a test file to upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("CLI staging workflow test content\n")
            temp_file = Path(f.name)

        try:
            # Step 1: Put artifact in staging mode
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "edit",
                    "--stage",
                    "--comment",
                    "CLI staging workflow test",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI edit failed: {result.stderr}"

            # Step 2: Upload file via CLI
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "put",
                    str(temp_file),
                    "/cli-staging-test.txt",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI upload failed: {result.stderr}"

            # Step 3: Commit changes
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "commit",
                    "--comment",
                    "CLI staging workflow commit",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI commit failed: {result.stderr}"

            # Step 4: Verify file exists
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "exists",
                    "/cli-staging-test.txt",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI exists check failed: {result.stderr}"

            # Step 5: Read file content
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "cat",
                    "/cli-staging-test.txt",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI cat command failed: {result.stderr}"
            assert "CLI staging workflow test content" in result.stdout

        finally:
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()

    def test_real_cli_multipart_upload(
        self,
        cli_env: dict[str, str],
        artifact_name: str,
        real_artifact: ArtifactCLI,  # noqa: ARG002
    ) -> None:
        """Test real CLI multipart upload with proper staging."""
        # Create a smaller test file for multipart upload (20MB)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            chunk = b"C" * (1024 * 1024)  # 1MB chunks
            for _ in range(20):
                f.write(chunk)
            large_file_path = Path(f.name)

        try:
            # Step 1: Put artifact in staging mode
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "edit",
                    "--stage",
                    "--comment",
                    "CLI multipart test",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI edit failed: {result.stderr}"

            multipart_config: MultipartConfig = {
                "enable": True,
                "threshold": 2 * 1024 * 1024,  # 2MB threshold
                "chunk_size": 6 * 1024 * 1024,  # 6MB chunks
            }

            multipart_config_str = json.dumps(multipart_config)

            # Step 2: Upload with CLI using multipart (smaller thresholds)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "put",
                    f"--multipart-config={multipart_config_str}",
                    str(large_file_path),
                    "/cli-multipart-test.bin",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )  # 2 min timeout

            # Handle connectivity issues
            if result.returncode != 0:
                error_output = result.stderr
                if (
                    "timeout" in error_output.lower()
                    or "connection" in error_output.lower()
                ):
                    pytest.skip(
                        f"Network connectivity issue during CLI upload: {error_output}",
                    )
                else:
                    pytest.fail(f"CLI multipart upload failed: {error_output}")

            # Step 3: Commit the upload
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "commit",
                    "--comment",
                    "CLI multipart upload commit",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI commit failed: {result.stderr}"

            # Step 4: Verify file info
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "info",
                    "/cli-multipart-test.bin",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI info command failed: {result.stderr}"

        finally:
            # Clean up temp file
            if large_file_path.exists():
                large_file_path.unlink()


class TestRealErrorHandling:
    """Test real error handling scenarios."""

    def test_missing_environment_variables(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test handling of missing environment variables."""
        # Unset variables
        monkeypatch.delenv("HYPHA_SERVER_URL", raising=False)
        monkeypatch.delenv("HYPHA_WORKSPACE", raising=False)
        monkeypatch.delenv("HYPHA_TOKEN", raising=False)

        # Try to get connection params
        with pytest.raises((SystemExit, ValueError)):
            get_connection_params()

    def test_nonexistent_artifact(self) -> None:
        """Test handling of nonexistent artifact."""
        # If creation fails or list fails, it should be caught
        with contextlib.suppress(Exception):
            artifact = ArtifactCLI("nonexistent-artifact-12345")
            # Try to list files - should fail gracefully
            artifact.ls("/", detail=True)

    def test_invalid_paths(self) -> None:
        """Test handling of invalid paths."""
        artifact = ArtifactCLI("test-cli-artifact")

        # Test invalid path operations
        with pytest.raises(OSError):  # noqa: PT011
            artifact.cat("/nonexistent-file.txt")

        with pytest.raises(HTTPError):
            artifact.info("/nonexistent-file.txt")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
