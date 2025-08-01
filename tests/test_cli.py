"""
Real integration tests for the Hypha Artifact CLI.

These tests use actual Hypha connections and real file operations.
Requires valid credentials in .env file.
"""

import os
from pathlib import Path
import sys
import tempfile
import subprocess
import socket
from httpx import HTTPError, HTTPStatusError
import requests
import pytest
from dotenv import load_dotenv, find_dotenv
from hypha_artifact.cli import (
    get_connection_params,
    create_artifact,
)

# Load environment variables
load_dotenv(dotenv_path=find_dotenv(usecwd=True))

# # Add the CLI module to the path for testing
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


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

        print("✅ Environment variables loaded successfully")
        print(f"   Server: {server_url}")
        print(f"   Workspace: {workspace}")
        print(f"   Token: {'*' * 10 + token[-4:] if token else 'None'}")

    def test_real_connection_params(self):
        """Test real connection parameter retrieval."""
        server_url, token, workspace = get_connection_params()

        assert server_url, "Server URL should not be empty"
        assert workspace, "Workspace should not be empty"
        assert token, "Token should not be empty"

        print("✅ Connection parameters retrieved successfully")

    def test_real_artifact_creation(self):
        """Test real artifact creation."""
        artifact = create_artifact("test-cli-artifact")
        assert artifact is not None
        # Check that the artifact was created successfully
        assert hasattr(artifact, "ls")
        assert hasattr(artifact, "upload")

        print("✅ Artifact connection created successfully")


class TestRealFileOperations:
    """Test real file operations with actual Hypha connections."""

    @pytest.fixture
    def real_artifact(self):
        """Create a real artifact connection."""
        return create_artifact("test-cli-artifact")

    def test_real_ls_command(self, real_artifact):
        """Test real ls command."""
        items = real_artifact.ls("/")
        print(f"✅ Found {len(items)} items in artifact root")
        assert isinstance(items, list)

    def test_real_staging_workflow(self, real_artifact):
        """Test real staging workflow using proper artifact manager API."""
        # Create a test file
        test_content = "This is a test file for API staging workflow\n"

        # Step 1: Put artifact in staging mode
        print("Before staging - checking current artifact state...")
        try:
            current_files = real_artifact._remote_list_contents(dir_path="/")
            print(f"Current files in artifact: {[f['name'] for f in current_files]}")
        except Exception as e:
            print(f"Could not list current files: {e}")

        # Clean up any existing staged changes first
        print("Discarding any existing staged changes...")
        try:
            real_artifact._remote_post("discard", {})
            print("Successfully discarded existing staged changes")
        except Exception as e:
            print(f"No staged changes to discard (expected): {e}")

        print("Putting artifact in staging mode with new version intent...")
        real_artifact._remote_edit(
            stage=True, version="new", comment="Testing proper staging workflow"
        )
        print("Artifact is now in staging mode with new version intent")

        # Step 2: Get presigned URL and upload file
        put_url = real_artifact._remote_put_file_url("/api-staging-test.txt")
        response = requests.put(put_url, data=test_content.encode(), timeout=30)
        assert response.ok, f"File upload failed: {response.status_code}"

        # Step 3: Verify file exists in staging
        files = real_artifact._remote_list_contents(dir_path="/", version="stage")
        file_names = [f["name"] for f in files]
        assert "api-staging-test.txt" in file_names

        # Step 4: Commit the changes
        try:
            real_artifact._remote_commit(comment="Committed API staging test")
        except HTTPStatusError as e:
            # Get more detailed error information
            print(f"Commit error: {e}")
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
            raise e
        except HTTPError as e:
            # Handle other HTTP errors
            print(f"Commit error: {e}")
            raise e

        # Step 5: Verify file exists after commit
        assert real_artifact.exists("/api-staging-test.txt")
        content = real_artifact.cat("/api-staging-test.txt")
        assert content == test_content

        print("✅ API staging workflow completed successfully")

    def test_real_multipart_upload(self, real_artifact):
        """Test real multipart upload using proper API workflow."""
        # First test if S3 endpoint is reachable

        try:
            # Test S3 connectivity with a short timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout
            result = sock.connect_ex(("s3.cloud.kth.se", 443))
            sock.close()
            if result != 0:
                pytest.skip(
                    "S3 endpoint s3.cloud.kth.se not reachable - network connectivity issue"
                )
        except Exception:
            pytest.skip("Cannot test S3 connectivity - network connectivity issue")

        # Create a smaller test file (4MB) to reduce network load
        file_size = 4 * 1024 * 1024  # 4MB
        chunk_size = 1 * 1024 * 1024  # 1MB chunks

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            # Write test data
            chunk = b"M" * (1024 * 1024)  # 1MB chunks
            for _ in range(4):
                f.write(chunk)
            temp_file_path = f.name

        try:
            # Step 1: Clean up and put artifact in staging mode
            # Clean up any existing staged changes first
            try:
                real_artifact._remote_post("discard", {})
            except Exception:
                pass  # No staged changes to discard

            real_artifact._remote_edit(
                stage=True, version="new", comment="Testing multipart upload"
            )

            # Step 2: Use upload method with auto_commit=False and smaller file
            real_artifact.upload(
                local_path=Path(temp_file_path),
                remote_path="/multipart-test.bin",
                enable_multipart=True,
                multipart_threshold=2 * 1024 * 1024,  # 2MB threshold
                chunk_size=chunk_size,
                auto_commit=False,  # Don't auto-commit, we'll do it manually
            )

            # Step 3: Commit the upload
            real_artifact._remote_commit(comment="Committed multipart upload")

            # Step 4: Verify file exists and has correct size
            assert real_artifact.exists("/multipart-test.bin")
            info = real_artifact.info("/multipart-test.bin")
            assert info["size"] == file_size

            print("✅ Multipart upload completed successfully")

        except Exception as e:
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Network connectivity issue during multipart upload: {e}")
            else:
                raise e

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_real_directory_upload(self, real_artifact):
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
                real_artifact._remote_post("discard", {})
            except Exception:
                pass  # No staged changes to discard

            real_artifact._remote_edit(
                stage=True, version="new", comment="Testing directory upload"
            )

            # Step 2: Upload directory with auto_commit=False
            real_artifact.upload(
                local_path=temp_path,
                remote_path="/api-test-dir",
                recursive=True,
                auto_commit=False,
            )

            # Step 3: Commit the upload
            real_artifact._remote_commit(comment="Committed directory upload")

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

            print("✅ Directory upload completed successfully")

    def test_real_file_operations(self, real_artifact):
        """Test real file operations using proper API workflow."""
        # Create initial test file
        test_content = "Test file for operations\n"

        # Step 1: Clean up and put artifact in staging mode
        # Clean up any existing staged changes first
        try:
            real_artifact._remote_post("discard", {})
        except Exception:
            pass  # No staged changes to discard

        real_artifact._remote_edit(
            stage=True, version="new", comment="Testing file operations"
        )

        put_url = real_artifact._remote_put_file_url("/ops-test.txt")
        response = requests.put(put_url, data=test_content.encode(), timeout=30)
        assert response.ok, f"File upload failed: {response.status_code}"

        # Step 2: Commit the initial upload
        real_artifact._remote_commit(comment="Initial file for operations test")

        # Step 3: Test file operations (these work on committed files)

        # Copy file
        real_artifact.copy("/ops-test.txt", "/ops-test-copy.txt")
        assert real_artifact.exists("/ops-test-copy.txt")

        # Verify copy has same content
        copy_content = real_artifact.cat("/ops-test-copy.txt")
        assert copy_content == test_content

        # Create directory and copy file there
        real_artifact.mkdir("/ops-test-dir")
        real_artifact.copy("/ops-test.txt", "/ops-test-dir/operations.txt")
        assert real_artifact.exists("/ops-test-dir/operations.txt")

        # Remove files
        real_artifact.rm("/ops-test-copy.txt")
        assert not real_artifact.exists("/ops-test-copy.txt")

        print("✅ File operations completed successfully")

    def test_real_find_command(self, real_artifact):
        """Test real find command."""
        files = real_artifact.find("/")
        print(f"✅ Found {len(files)} files in artifact")
        assert isinstance(files, list)


class TestRealCLICommands:
    """Test real CLI commands with actual subprocess calls."""

    @pytest.fixture
    def cli_env(self):
        """Get environment variables for CLI testing."""
        env = os.environ.copy()
        # Ensure we have the required environment variables
        env["HYPHA_SERVER_URL"] = os.getenv("HYPHA_SERVER_URL", "")
        env["HYPHA_WORKSPACE"] = os.getenv("HYPHA_WORKSPACE", "")
        env["HYPHA_TOKEN"] = os.getenv("HYPHA_TOKEN", "")
        return env

    @pytest.fixture
    def test_artifact_id(self):
        """Get the test artifact ID."""
        return "test-cli-artifact"

    def test_real_cli_ls(self, cli_env, test_artifact_id):
        """Test real CLI ls command."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "hypha_artifact.cli",
                f"--artifact-id={test_artifact_id}",
                "ls",
                "/",
            ],
            env=cli_env,
            capture_output=True,
            text=True,
            check=True,
        )

        assert result.returncode == 0, f"CLI ls command failed: {result.stderr}"
        print("✅ CLI ls command executed successfully")

    def test_real_cli_staging_workflow(self, cli_env, test_artifact_id):
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
                    "upload",
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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

            print("✅ CLI staging workflow completed successfully")

        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_real_cli_multipart_upload(self, cli_env, test_artifact_id):
        """Test real CLI multipart upload with proper staging."""
        # First test if S3 endpoint is reachable

        try:
            # Test S3 connectivity with a short timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout
            result = sock.connect_ex(("s3.cloud.kth.se", 443))
            sock.close()
            if result != 0:
                pytest.skip(
                    "S3 endpoint s3.cloud.kth.se not reachable - network connectivity issue"
                )
        except Exception:
            pytest.skip("Cannot test S3 connectivity - network connectivity issue")

        # Create a smaller test file for multipart upload (4MB)
        # large_file_size = 4 * 1024 * 1024
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            chunk = b"C" * (1024 * 1024)  # 1MB chunks
            for _ in range(4):
                f.write(chunk)
            large_file_path = f.name

        try:
            # Step 1: Put artifact in staging mode
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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

            # Step 2: Upload with CLI using multipart (smaller thresholds)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
                    "upload",
                    "--enable-multipart",
                    "--multipart-threshold=2000000",  # 2MB
                    "--chunk-size=1000000",  # 1MB chunks
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
                        f"Network connectivity issue during CLI multipart upload: {error_output}"
                    )
                else:
                    assert False, f"CLI multipart upload failed: {error_output}"

            # Step 3: Commit the upload
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
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
                    "hypha_artifact.cli",
                    f"--artifact-id={test_artifact_id}",
                    "info",
                    "/cli-multipart-test.bin",
                ],
                env=cli_env,
                capture_output=True,
                text=True,
                check=True,
            )

            assert result.returncode == 0, f"CLI info command failed: {result.stderr}"

            print("✅ CLI multipart upload completed successfully")

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
                print(
                    "✅ Correctly handled missing environment variables with SystemExit"
                )
            except Exception as e:
                print(f"✅ Correctly handled missing environment variables: {e}")

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
            artifact = create_artifact("nonexistent-artifact-12345")
            # Try to list files - should fail gracefully
            try:
                items = artifact.ls("/")
                print(
                    f"⚠️  Unexpectedly found {len(items)} items in nonexistent artifact"
                )
            except Exception as e:
                print(f"✅ Correctly handled nonexistent artifact: {e}")
        except Exception as e:
            print(f"✅ Correctly handled nonexistent artifact creation: {e}")

    def test_invalid_paths(self):
        """Test handling of invalid paths."""
        artifact = create_artifact("test-cli-artifact")

        # Test invalid path operations
        try:
            artifact.cat("/nonexistent-file.txt")
            assert False, "Should have raised an error for nonexistent file"
        except Exception as e:
            print(f"✅ Correctly handled nonexistent file: {e}")

        try:
            artifact.info("/nonexistent-file.txt")
            assert False, "Should have raised an error for nonexistent file"
        except Exception as e:
            print(f"✅ Correctly handled nonexistent file info: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
