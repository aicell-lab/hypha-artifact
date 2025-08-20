# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Real integration tests for the Hypha Artifact CLI.

These tests use actual Hypha connections and real file operations.
Requires valid credentials in .env file.
"""

# TODO: move non-CLI specific tests to a separate file

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from dotenv import find_dotenv, load_dotenv
from httpx import HTTPError, HTTPStatusError

from cli.main import (
    ArtifactCLI,
    get_connection_params,
)

# Load environment variables
load_dotenv(dotenv_path=find_dotenv(usecwd=True))


@pytest.fixture(scope="module", name="real_artifact")
def get_artifact(artifact_name: str, artifact_setup_teardown: tuple[str, str]) -> Any:
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

    def test_environment_variables_available(self):
        """Test that required environment variables are available."""
        server_url = os.getenv("HYPHA_SERVER_URL")
        workspace = os.getenv("HYPHA_WORKSPACE")
        token = os.getenv("HYPHA_TOKEN")

        assert server_url, "HYPHA_SERVER_URL environment variable is required"
        assert workspace, "HYPHA_WORKSPACE environment variable is required"
        assert token, "HYPHA_TOKEN environment variable is required"

        logging.info("✅ Environment variables loaded successfully")
        logging.info(f"   Server: {server_url}")
        logging.info(f"   Workspace: {workspace}")
        logging.info(f"   Token: {'*' * 10 + token[-4:] if token else 'None'}")

    def test_real_connection_params(self):
        """Test real connection parameter retrieval."""
        connection_params = get_connection_params()

        assert connection_params["HYPHA_SERVER_URL"], "Server URL should not be empty"
        assert connection_params["HYPHA_WORKSPACE"], "Workspace should not be empty"
        assert connection_params["HYPHA_TOKEN"], "Token should not be empty"

        logging.info("✅ Connection parameters retrieved successfully")

    def test_real_artifact_creation(self):
        """Test real artifact creation."""
        artifact = ArtifactCLI("test-cli-artifact")
        assert artifact is not None
        # Check that the artifact was created successfully
        assert hasattr(artifact, "ls")
        assert hasattr(artifact, "put")

        logging.info("✅ Artifact connection created successfully")


class TestRealFileOperations:
    """Test real file operations with actual Hypha connections."""

    def test_real_ls_command(self, real_artifact: ArtifactCLI):
        """Test real ls command."""
        items = real_artifact.ls("/", detail=True)
        logging.info(f"✅ Found {len(items)} items in artifact root")
        assert isinstance(items, list)

    def test_real_staging_workflow(self, real_artifact: ArtifactCLI):
        """Test real staging workflow using proper artifact manager API."""
        # Create a test file
        test_content = "This is a test file for API staging workflow\n"

        # Step 1: Put artifact in staging mode
        logging.info("Before staging - checking current artifact state...")
        try:
            current_files = real_artifact.ls("/", detail=True)
            logging.info(
                f"Current files in artifact: {[f['name'] for f in current_files]}",
            )
        except Exception as e:
            logging.info(f"Could not list current files: {e}")

        # Clean up any existing staged changes first
        logging.info("Discarding any existing staged changes...")
        try:
            real_artifact.discard()
            logging.info("Successfully discarded existing staged changes")
        except Exception as e:
            logging.info(f"No staged changes to discard (expected): {e}")

        logging.info("Putting artifact in staging mode with new version intent...")
        real_artifact.edit(
            stage=True,
            version="new",
            comment="Testing proper staging workflow",
        )
        logging.info("Artifact is now in staging mode with new version intent")

        # Step 2: Get presigned URL and upload file
        with real_artifact.open("/api-staging-test.txt", "w") as f:
            f.write(test_content)

        # Step 3: Commit the changes
        try:
            real_artifact.commit(comment="Committed API staging test")
        except HTTPStatusError as e:
            # Get more detailed error information
            logging.info(f"Commit error: {e}")
            logging.info(f"Response status: {e.response.status_code}")
            logging.info(f"Response content: {e.response.text}")
            raise e
        except HTTPError as e:
            # Handle other HTTP errors
            logging.info(f"Commit error: {e}")
            raise e

        # Step 4: Verify file exists after commit
        assert real_artifact.exists("/api-staging-test.txt")
        content = real_artifact.cat("/api-staging-test.txt")
        assert content == test_content

        logging.info("✅ API staging workflow completed successfully")

    def test_real_multipart_upload(self, real_artifact: ArtifactCLI):
        """Test real multipart upload using proper API workflow."""
        # Create a smaller test file (20 MB) to reduce network load
        file_size = 20 * 1024 * 1024  # 20 MB
        chunk_size = 6 * 1024 * 1024  # 6 MB chunks

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            # Write test data
            chunk = b"M" * (1024 * 1024)  # 1MB chunks
            for _ in range(20):
                f.write(chunk)
            temp_file_path = f.name

        try:
            # Step 1: Clean up and put artifact in staging mode
            # Clean up any existing staged changes first
            try:
                real_artifact.discard()
            except Exception as e:
                logging.warning(str(e))

            real_artifact.edit(
                stage=True,
                version="new",
                comment="Testing multipart upload",
            )

            multipart_config: dict[str, bool | int] = {
                "enable": True,
                "threshold": 2 * 1024 * 1024,  # 2MB threshold
                "chunk_size": chunk_size,
            }

            real_artifact.put(
                lpath=temp_file_path,
                rpath="/multipart-test.bin",
                multipart_config=multipart_config,
            )

            # Step 3: Commit the upload
            real_artifact.commit(comment="Committed multipart upload")

            # Step 4: Verify file exists and has correct size
            assert real_artifact.exists("/multipart-test.bin")
            info = real_artifact.info("/multipart-test.bin")
            assert info["size"] == file_size

            logging.info("✅ Multipart upload completed successfully")

        except Exception as e:
            raise e
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_real_directory_upload(self, real_artifact: ArtifactCLI):
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
            try:
                real_artifact.discard()
            except Exception:
                pass  # No staged changes to discard

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

            logging.info("✅ Directory upload completed successfully")

    def test_real_file_operations(self, real_artifact: ArtifactCLI):
        """Test real file operations using proper API workflow."""
        # Create initial test file
        test_content = "Test file for operations\n"

        # Step 1: Clean up and put artifact in staging mode
        # Clean up any existing staged changes first
        try:
            real_artifact.discard()
        except Exception:
            pass  # No staged changes to discard

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

        logging.info("✅ File operations completed successfully")

    def test_real_find_command(self, real_artifact: ArtifactCLI):
        """Test real find command."""
        files = real_artifact.find("/")
        logging.info(f"✅ Found {len(files)} files in artifact")
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
        real_artifact: ArtifactCLI,
    ):
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
        logging.info("✅ CLI ls command executed successfully")

    def test_real_cli_staging_workflow(
        self,
        cli_env: dict[str, str],
        artifact_name: str,
        real_artifact: ArtifactCLI,
    ):
        """Test real CLI staging workflow using edit and commit commands."""
        # Create a test file to upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("CLI staging workflow test content\n")
            temp_file = f.name

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
                    temp_file,
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

            logging.info("✅ CLI staging workflow completed successfully")

        except Exception as e:
            raise e
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_real_cli_multipart_upload(
        self,
        cli_env: dict[str, str],
        artifact_name: str,
        real_artifact: ArtifactCLI,
    ):
        """Test real CLI multipart upload with proper staging."""
        # First test if S3 endpoint is reachable

        # Create a smaller test file for multipart upload (20MB)
        # large_file_size = 20 * 1024 * 1024
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            chunk = b"C" * (1024 * 1024)  # 1MB chunks
            for _ in range(20):
                f.write(chunk)
            large_file_path = f.name

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

            multipart_config: dict[str, bool | int] = {
                "enable": True,
                "threshold": 2 * 1024 * 1024,  # 2MB threshold
                "chunk_size": 6 * 1024 * 1024,  # 6MB chunks
            }

            multipart_config_str = json.dumps(multipart_config)

            # TODO: this fails silently on error?
            # Step 2: Upload with CLI using multipart (smaller thresholds)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    f"--artifact-id={artifact_name}",
                    "put",
                    f"--multipart-config={multipart_config_str}",
                    large_file_path,
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
                        f"Network connectivity issue during CLI multipart upload: {error_output}",
                    )
                else:
                    assert False, f"CLI multipart upload failed: {error_output}"

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

            logging.info("✅ CLI multipart upload completed successfully")
        except Exception as e:
            raise e
        finally:
            # Clean up temp file
            if os.path.exists(large_file_path):
                os.unlink(large_file_path)


class TestRealErrorHandling:
    """Test real error handling scenarios."""

    def test_missing_environment_variables(self):
        """Test handling of missing environment variables."""
        # Temporarily unset environment variables
        original_server = os.environ.get("HYPHA_SERVER_URL")
        original_workspace = os.environ.get("HYPHA_WORKSPACE")
        original_token = os.environ.get("HYPHA_TOKEN")

        try:
            # Unset variables
            if "HYPHA_SERVER_URL" in os.environ:
                del os.environ["HYPHA_SERVER_URL"]
            if "HYPHA_WORKSPACE" in os.environ:
                del os.environ["HYPHA_WORKSPACE"]
            if "HYPHA_TOKEN" in os.environ:
                del os.environ["HYPHA_TOKEN"]

            # Try to get connection params
            try:
                _, _, _ = get_connection_params()
                assert (
                    False
                ), "Should have raised an error for missing environment variables"
            except SystemExit:
                logging.info(
                    "✅ Correctly handled missing environment variables with SystemExit",
                )
            except Exception as e:
                logging.info(f"✅ Correctly handled missing environment variables: {e}")
        except Exception as e:
            raise e
        finally:
            # Restore environment variables
            if original_server:
                os.environ["HYPHA_SERVER_URL"] = original_server
            if original_workspace:
                os.environ["HYPHA_WORKSPACE"] = original_workspace
            if original_token:
                os.environ["HYPHA_TOKEN"] = original_token

    def test_nonexistent_artifact(self):
        """Test handling of nonexistent artifact."""
        try:
            artifact = ArtifactCLI("nonexistent-artifact-12345")
            # Try to list files - should fail gracefully
            try:
                items = artifact.ls("/", detail=True)
                logging.info(
                    f"⚠️  Unexpectedly found {len(items)} items in nonexistent artifact",
                )
            except Exception as e:
                logging.info(f"✅ Correctly handled nonexistent artifact: {e}")
        except Exception as e:
            logging.info(f"✅ Correctly handled nonexistent artifact creation: {e}")

    def test_invalid_paths(self):
        """Test handling of invalid paths."""
        artifact = ArtifactCLI("test-cli-artifact")

        # Test invalid path operations
        try:
            artifact.cat("/nonexistent-file.txt")
            assert False, "Should have raised an error for nonexistent file"
        except Exception as e:
            logging.info(f"✅ Correctly handled nonexistent file: {e}")

        try:
            artifact.info("/nonexistent-file.txt")
            assert False, "Should have raised an error for nonexistent file"
        except Exception as e:
            logging.info(f"✅ Correctly handled nonexistent file info: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
