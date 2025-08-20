"""Integration tests for the HyphaArtifact module.

This module contains integration tests for the HyphaArtifact class,
testing real file operations such as creation, reading, copying, and deletion
against an actual Hypha artifact service.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from hypha_artifact import HyphaArtifact
from tests.conftest import ArtifactTestMixin


@pytest.fixture(scope="module", name="artifact")
def get_artifact(artifact_name: str, artifact_setup_teardown: tuple[str, str]) -> Any:
    """Create a test artifact with a real connection to Hypha."""
    token, workspace = artifact_setup_teardown
    return HyphaArtifact(
        artifact_name,
        workspace,
        token,
        server_url="https://hypha.aicell.io",
    )


class TestHyphaArtifactIntegration(ArtifactTestMixin):
    """Integration test suite for the HyphaArtifact class."""

    def test_create_file(self, artifact: HyphaArtifact, test_content: str) -> None:
        """Test creating a file in the artifact using real operations."""
        test_file_path = "test_file.txt"

        # Create a test file
        artifact.edit(stage=True)
        with artifact.open(test_file_path, "w") as f:
            f.write(test_content)
        artifact.commit()

        # Verify the file was created
        files = artifact.ls("/", detail=True)
        file_names = [f["name"] for f in files]
        assert (
            test_file_path in file_names
        ), f"Created file {test_file_path} not found in {file_names}"

    def test_list_files(self, artifact: HyphaArtifact) -> None:
        """Test listing files in the artifact using real operations."""
        # First, list files with detail=True (default)
        files = artifact.ls("/", detail=True)
        self._validate_file_listing(files)

        # Test listing with detail=False
        file_names: list[str] = artifact.ls("/", detail=False)
        self._validate_file_listing(file_names)

    def test_read_file_content(
        self,
        artifact: HyphaArtifact,
        test_content: str,
    ) -> None:
        """Test reading content from a file in the artifact using real operations."""
        test_file_path = "test_file.txt"

        # Ensure the test file exists (create if needed)
        if not artifact.exists(test_file_path):
            artifact.edit(stage=True)
            with artifact.open(test_file_path, "w") as f:
                f.write(test_content)
            artifact.commit()

        # Read the file content
        content = artifact.cat(test_file_path)
        self._validate_file_content(content, test_content)

    def test_copy_file(self, artifact: HyphaArtifact, test_content: str) -> None:
        """Test copying a file within the artifact using real operations."""
        source_path = "source_file.txt"
        copy_path = "copy_of_source_file.txt"

        # Create a source file if it doesn't exist
        if not artifact.exists(source_path):
            artifact.edit(stage=True)
            with artifact.open(source_path, "w") as f:
                f.write(test_content)
            artifact.commit()

        assert artifact.exists(
            source_path,
        ), f"Source file {source_path} should exist before copying"

        # Copy the file
        artifact.edit(stage=True)
        artifact.copy(source_path, copy_path)
        artifact.commit()
        self._validate_copy_operation(artifact, source_path, copy_path, test_content)

    def test_file_existence(self, artifact: HyphaArtifact) -> None:
        """Test checking if files exist in the artifact using real operations."""
        # Create a test file to check existence
        test_file_path = "existence_test.txt"
        artifact.edit(stage=True)
        with artifact.open(test_file_path, "w") as f:
            f.write("Testing file existence")
        artifact.commit()

        # Test for existing file
        self._validate_file_existence(artifact, test_file_path, True)

        # Test for non-existent file
        non_existent_path = "this_file_does_not_exist.txt"
        self._validate_file_existence(artifact, non_existent_path, False)

    def test_remove_file(self, artifact: HyphaArtifact) -> None:
        """Test removing a file from the artifact using real operations."""
        # Create a file to be removed
        removal_test_file = "file_to_remove.txt"

        # Ensure the file exists first
        artifact.edit(stage=True)
        with artifact.open(removal_test_file, "w") as f:
            f.write("This file will be removed")
        artifact.commit()

        # Verify file exists before removal
        self._validate_file_existence(artifact, removal_test_file, True)

        # Remove the file
        artifact.edit(stage=True)
        artifact.rm(removal_test_file)
        artifact.commit()

        # Verify file no longer exists
        self._validate_file_existence(artifact, removal_test_file, False)

    def test_workflow(self, artifact: HyphaArtifact, test_content: str) -> None:
        """Integration test for a complete file workflow: create, read, copy, remove."""
        # File paths for testing
        original_file = "workflow_test.txt"
        copied_file = "workflow_test_copy.txt"

        # Step 1: Create file
        artifact.edit(stage=True)
        with artifact.open(original_file, "w") as f:
            f.write(test_content)
        artifact.commit()

        # Step 2: Verify file exists and content is correct
        assert artifact.exists(original_file)
        content = artifact.cat(original_file)
        self._validate_file_content(content, test_content)

        # Step 3: Copy file
        artifact.edit(stage=True)
        artifact.copy(original_file, copied_file)
        artifact.commit()
        assert artifact.exists(copied_file)
        logging.info(artifact.ls("/", detail=True))

        # Step 4: Remove copied file
        artifact.edit(stage=True)
        artifact.rm(copied_file)
        artifact.commit()
        self._validate_file_existence(artifact, copied_file, False)
        assert artifact.exists(original_file)

    def test_partial_file_read(
        self,
        artifact: HyphaArtifact,
        test_content: str,
    ) -> None:
        """Test reading only part of a file using the size parameter in read."""
        test_file_path = "partial_read_test.txt"

        # Create a test file
        artifact.edit(stage=True)
        with artifact.open(test_file_path, "w") as f:
            f.write(test_content)
        artifact.commit()

        # Read only the first 10 bytes of the file
        with artifact.open(test_file_path, "r") as f:
            partial_content = f.read(10)

        # Verify the partial content matches the expected first 10 bytes
        expected_content = test_content[:10]
        self._validate_file_content(partial_content, expected_content)

    def test_get_file(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying a file from remote (artifact) to local filesystem."""
        remote_file = "sync_get_test_file.txt"
        local_file = tmp_path / "local_get_test_file.txt"

        # Create a test file in the artifact
        artifact.edit(stage=True)
        with artifact.open(remote_file, "w") as f:
            f.write(test_content)
        artifact.commit()

        # Copy from remote to local
        artifact.get(remote_file, str(local_file))

        # Verify local file exists and has correct content
        assert local_file.exists(), f"Local file {local_file} should exist"
        with open(local_file, encoding="utf-8") as f:
            local_content = f.read()
        self._validate_file_content(local_content, test_content)

    def test_put_file(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying a file from local filesystem to remote (artifact)."""
        local_file = tmp_path / "local_put_test_file.txt"
        remote_file = "sync_put_test_file.txt"

        # Create a test file locally
        with open(local_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        # Copy from local to remote
        artifact.edit(stage=True)
        artifact.put(str(local_file), remote_file)
        artifact.commit()

        # Verify remote file exists and has correct content
        assert artifact.exists(remote_file), f"Remote file {remote_file} should exist"
        remote_content = artifact.cat(remote_file)
        self._validate_file_content(remote_content, test_content)

    def test_get_directory_recursive(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying a directory recursively from remote to local."""
        remote_dir = "sync_get_dir"
        remote_file1 = f"{remote_dir}/file1.txt"
        remote_file2 = f"{remote_dir}/subdir/file2.txt"
        local_dir = tmp_path / "local_get_dir"

        # Create test files in the artifact
        artifact.edit(stage=True)
        with artifact.open(remote_file1, "w") as f:
            f.write(test_content + "_1")
        with artifact.open(remote_file2, "w") as f:
            f.write(test_content + "_2")
        artifact.commit()

        # Copy directory recursively from remote to local
        artifact.get(remote_dir, str(local_dir), recursive=True)

        # Verify local files exist and have correct content
        local_file1 = local_dir / "file1.txt"
        local_file2 = local_dir / "subdir" / "file2.txt"

        assert local_file1.exists(), f"Local file {local_file1} should exist"
        assert local_file2.exists(), f"Local file {local_file2} should exist"

        with open(local_file1, encoding="utf-8") as f:
            content1 = f.read()
        with open(local_file2, encoding="utf-8") as f:
            content2 = f.read()

        self._validate_file_content(content1, test_content + "_1")
        self._validate_file_content(content2, test_content + "_2")

    def test_put_directory_recursive(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying a directory recursively from local to remote."""
        local_dir = tmp_path / "local_put_dir"
        local_subdir = local_dir / "subdir"
        local_file1 = local_dir / "file1.txt"
        local_file2 = local_subdir / "file2.txt"
        remote_dir = "sync_put_dir"

        # Create test directory structure locally
        local_subdir.mkdir(parents=True, exist_ok=True)
        with open(local_file1, "w", encoding="utf-8") as f:
            f.write(test_content + "_1")
        with open(local_file2, "w", encoding="utf-8") as f:
            f.write(test_content + "_2")

        # Copy directory recursively from local to remote
        artifact.edit(stage=True)
        artifact.put(str(local_dir), remote_dir, recursive=True)
        artifact.commit()

        # Verify remote files exist and have correct content
        remote_file1 = f"{remote_dir}/file1.txt"
        remote_file2 = f"{remote_dir}/subdir/file2.txt"

        assert artifact.exists(remote_file1), f"Remote file {remote_file1} should exist"
        assert artifact.exists(remote_file2), f"Remote file {remote_file2} should exist"

        content1 = artifact.cat(remote_file1)
        content2 = artifact.cat(remote_file2)

        self._validate_file_content(content1, test_content + "_1")
        self._validate_file_content(content2, test_content + "_2")

    def test_get_multiple_files(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying multiple files from remote to local using lists."""
        remote_files = ["sync_get_multi1.txt", "sync_get_multi2.txt"]
        local_files = [
            str(tmp_path / "local_get_multi1.txt"),
            str(tmp_path / "local_get_multi2.txt"),
        ]

        # Create test files in the artifact
        artifact.edit(stage=True)
        for i, remote_file in enumerate(remote_files):
            with artifact.open(remote_file, "w") as f:
                f.write(test_content + f"_{i+1}")
        artifact.commit()

        # Copy multiple files from remote to local
        artifact.get(remote_files, local_files)

        # Verify local files exist and have correct content
        for i, local_file in enumerate(local_files):
            assert os.path.exists(local_file), f"Local file {local_file} should exist"
            with open(local_file, encoding="utf-8") as f:
                content = f.read()
            self._validate_file_content(content, test_content + f"_{i+1}")

    def test_put_multiple_files(
        self,
        artifact: HyphaArtifact,
        test_content: str,
        tmp_path: Path,
    ) -> None:
        """Test copying multiple files from local to remote using lists."""
        local_files = [
            str(tmp_path / "local_put_multi1.txt"),
            str(tmp_path / "local_put_multi2.txt"),
        ]
        remote_files = ["sync_put_multi1.txt", "sync_put_multi2.txt"]

        # Create test files locally
        for i, local_file in enumerate(local_files):
            with open(local_file, "w", encoding="utf-8") as f:
                f.write(test_content + f"_{i+1}")

        # Copy multiple files from local to remote
        artifact.edit(stage=True)
        artifact.put(local_files, remote_files)
        artifact.commit()

        # Verify remote files exist and have correct content
        for i, remote_file in enumerate(remote_files):
            assert artifact.exists(
                remote_file,
            ), f"Remote file {remote_file} should exist"
            content = artifact.cat(remote_file)
            self._validate_file_content(content, test_content + f"_{i+1}")

    def test_multipart_upload_large_file(self, artifact: HyphaArtifact) -> None:
        """Test multipart upload with a large file."""
        multipart_config: dict[str, bool | int] = {
            "enable": True,
            "threshold": 1024,  # 1MB threshold
            "chunk_size": 10 * 1024 * 1024,  # 10MB chunks
        }

        # Create a temporary large file (20MB to test multipart)
        file_size = 20 * 1024 * 1024  # 20MB total

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write test data in chunks
            test_data = b"A" * 1024  # 1KB of 'A's
            for _ in range(file_size // len(test_data)):
                temp_file.write(test_data)
            temp_file_path = temp_file.name

        try:
            remote_path = "large_multipart_test.bin"

            # Upload using multipart
            artifact.edit(stage=True)
            artifact.put(
                temp_file_path,
                remote_path,
                multipart_config=multipart_config,
            )
            artifact.commit()

            # Verify the file exists
            assert artifact.exists(
                remote_path,
            ), f"Uploaded file {remote_path} should exist"

            # Verify file size matches
            info = artifact.info(remote_path)
            assert (
                info.get("size") == file_size
            ), f"File size should be {file_size} bytes"

            # Clean up remote file
            artifact.edit(stage=True)
            artifact.rm(remote_path)
            artifact.commit()
        except Exception as e:
            raise e
        finally:
            # Clean up local temp file
            os.unlink(temp_file_path)

    def test_upload_folder(self, artifact: HyphaArtifact) -> None:
        """Test uploading a folder with multiple files."""
        # Create a temporary folder structure
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.txt").write_text("Content of file 1")
            (temp_path / "file2.txt").write_text("Content of file 2")

            # Create subdirectory
            subdir = temp_path / "subdir"
            subdir.mkdir()
            (subdir / "file3.txt").write_text("Content of file 3")

            # Upload folder
            remote_folder = "test_folder_upload"
            artifact.edit(stage=True)
            artifact.put(
                str(temp_path),
                remote_folder,
                recursive=True,
            )
            artifact.commit()

            # Verify files were uploaded
            files = artifact.ls(remote_folder)
            expected_files = {"file1.txt", "file2.txt", "subdir"}
            actual_files = set(files)

            assert expected_files.issubset(
                actual_files,
            ), f"Expected files {expected_files} not found in {actual_files}"

            # Verify subdirectory file
            subdir_files = artifact.ls(f"{remote_folder}/subdir")
            assert "file3.txt" in subdir_files, "Subdirectory file should be uploaded"

            # Verify file contents
            content1 = artifact.cat(f"{remote_folder}/file1.txt")
            assert content1 == "Content of file 1", "File content should match"

            # Clean up
            artifact.edit(stage=True)
            artifact.rm(f"{remote_folder}/file1.txt")
            artifact.rm(f"{remote_folder}/file2.txt")
            artifact.rm(f"{remote_folder}/subdir/file3.txt")
            artifact.commit()
