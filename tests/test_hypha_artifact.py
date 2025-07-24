"""
Integration tests for the HyphaArtifact module.

This module contains integration tests for the HyphaArtifact class,
testing real file operations such as creation, reading, copying, and deletion
against an actual Hypha artifact service.
"""

from typing import Any
from pathlib import Path
import pytest
from conftest import ArtifactTestMixin
from hypha_artifact import HyphaArtifact


@pytest.fixture(scope="module", name="artifact")
def get_artifact(artifact_name: str, artifact_setup_teardown: tuple[str, str]) -> Any:
    """Create a test artifact with a real connection to Hypha."""
    token, workspace = artifact_setup_teardown
    return HyphaArtifact(artifact_name, workspace, token)


class TestHyphaArtifactIntegration(ArtifactTestMixin):
    """Integration test suite for the HyphaArtifact class."""

    def test_artifact_initialization(
        self, artifact: HyphaArtifact, artifact_name: str
    ) -> None:
        """Test that the artifact is initialized correctly with real credentials."""
        self._check_artifact_initialization(artifact, artifact_name)

    def test_create_file(self, artifact: HyphaArtifact, test_content: str) -> None:
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

    def test_list_files(self, artifact: HyphaArtifact) -> None:
        """Test listing files in the artifact using real operations."""
        # First, list files with detail=True (default)
        files = artifact.ls("/")
        self._validate_file_listing(files)

        # Test listing with detail=False
        file_names: list[str] = artifact.ls("/", detail=False)
        self._validate_file_listing(file_names)

    def test_read_file_content(
        self, artifact: HyphaArtifact, test_content: str
    ) -> None:
        """Test reading content from a file in the artifact using real operations."""
        test_file_path = "test_file.txt"

        # Ensure the test file exists (create if needed)
        if not artifact.exists(test_file_path):
            with artifact.open(test_file_path, "w") as f:
                f.write(test_content)

        # Read the file content
        content = artifact.cat(test_file_path)
        self._validate_file_content(content, test_content)

    def test_copy_file(self, artifact: HyphaArtifact, test_content: str) -> None:
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
        self._validate_copy_operation(artifact, source_path, copy_path, test_content)

    def test_file_existence(self, artifact: HyphaArtifact) -> None:
        """Test checking if files exist in the artifact using real operations."""
        # Create a test file to check existence
        test_file_path = "existence_test.txt"
        with artifact.open(test_file_path, "w") as f:
            f.write("Testing file existence")

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
        with artifact.open(removal_test_file, "w") as f:
            f.write("This file will be removed")

        # Verify file exists before removal
        self._validate_file_existence(artifact, removal_test_file, True)

        # Remove the file
        artifact.rm(removal_test_file)

        # Verify file no longer exists
        self._validate_file_existence(artifact, removal_test_file, False)

    def test_workflow(self, artifact: HyphaArtifact, test_content: str) -> None:
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
        self._validate_file_content(content, test_content)

        # Step 3: Copy file
        artifact.copy(original_file, copied_file)
        assert artifact.exists(copied_file)
        print(artifact.ls("/"))

        # Step 4: Remove copied file
        artifact.rm(copied_file)
        self._validate_file_existence(artifact, copied_file, False)
        assert artifact.exists(original_file)

    def test_partial_file_read(
        self, artifact: HyphaArtifact, test_content: str
    ) -> None:
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
        self._validate_file_content(partial_content, expected_content)

    def test_multipart_upload_large_file(self, artifact: Any) -> None:
        """Test multipart upload with a large file."""
        import tempfile
        import os
        
        # Create a temporary large file (20MB to test multipart)
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        file_size = 20 * 1024 * 1024   # 20MB total
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write test data in chunks
            test_data = b"A" * 1024  # 1KB of 'A's
            for _ in range(file_size // len(test_data)):
                temp_file.write(test_data)
            temp_file_path = temp_file.name
        
        try:
            remote_path = "large_multipart_test.bin"
            
            # Upload using multipart
            artifact.upload(
                temp_file_path,
                remote_path,
                enable_multipart=True,
                chunk_size=chunk_size,
                multipart_threshold=1024,  # Low threshold to force multipart
            )
            
            # Verify the file exists
            assert artifact.exists(remote_path), f"Uploaded file {remote_path} should exist"
            
            # Verify file size matches
            info = artifact.info(remote_path)
            assert info.get("size") == file_size, f"File size should be {file_size} bytes"
            
            # Clean up remote file
            artifact.rm(remote_path)
            
        finally:
            # Clean up local temp file
            os.unlink(temp_file_path)

    def test_upload_folder(self, artifact: Any) -> None:
        """Test uploading a folder with multiple files."""
        import tempfile
        import os
        
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
            artifact.upload(
                temp_path,
                remote_folder,
                recursive=True,
            )
            
            # Verify files were uploaded
            files = artifact.ls(remote_folder, detail=False)
            expected_files = {"file1.txt", "file2.txt", "subdir"}
            actual_files = set(files)
            
            assert expected_files.issubset(actual_files), f"Expected files {expected_files} not found in {actual_files}"
            
            # Verify subdirectory file
            subdir_files = artifact.ls(f"{remote_folder}/subdir", detail=False)
            assert "file3.txt" in subdir_files, "Subdirectory file should be uploaded"
            
            # Verify file contents
            content1 = artifact.cat(f"{remote_folder}/file1.txt")
            assert content1 == "Content of file 1", "File content should match"
            
            # Clean up
            artifact.rm(f"{remote_folder}/file1.txt")
            artifact.rm(f"{remote_folder}/file2.txt")
            artifact.rm(f"{remote_folder}/subdir/file3.txt")
