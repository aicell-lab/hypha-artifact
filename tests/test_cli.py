"""
Comprehensive tests for the Hypha Artifact CLI.

This module tests the CLI interface including argument parsing, environment loading,
command execution, and error handling.
"""

import os
import sys
import json
import tempfile
import argparse
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path
from typing import Any, Dict, List
import pytest

# Add the CLI module to the path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hypha_artifact.cli import (
    main,
    get_connection_params,
    create_artifact,
    format_file_listing,
    cmd_ls,
    cmd_cat,
    cmd_cp,
    cmd_rm,
    cmd_mkdir,
    cmd_info,
    cmd_find,
    cmd_head,
    cmd_size,
    cmd_exists,
    cmd_upload,
    cmd_download,
)


class TestEnvironmentLoading:
    """Test environment variable loading and connection parameters."""

    def test_get_connection_params_success(self):
        """Test successful retrieval of connection parameters."""
        with patch.dict(os.environ, {
            'HYPHA_SERVER_URL': 'https://test.hypha.io',
            'HYPHA_TOKEN': 'test-token',
            'HYPHA_WORKSPACE': 'test-workspace'
        }):
            server_url, token, workspace = get_connection_params()
            assert server_url == 'https://test.hypha.io'
            assert token == 'test-token'
            assert workspace == 'test-workspace'

    def test_get_connection_params_missing_server_url(self):
        """Test error when HYPHA_SERVER_URL is missing."""
        with patch.dict(os.environ, {
            'HYPHA_TOKEN': 'test-token',
            'HYPHA_WORKSPACE': 'test-workspace'
        }, clear=True):
            with pytest.raises(SystemExit):
                get_connection_params()

    def test_get_connection_params_missing_workspace(self):
        """Test error when HYPHA_WORKSPACE is missing."""
        with patch.dict(os.environ, {
            'HYPHA_SERVER_URL': 'https://test.hypha.io',
            'HYPHA_TOKEN': 'test-token'
        }, clear=True):
            with pytest.raises(SystemExit):
                get_connection_params()

    def test_dotenv_loading(self):
        """Test that dotenv loading is called on import."""
        # This test verifies the import structure includes dotenv loading
        # Since load_dotenv is called at module level, we can't easily mock it
        # but we can verify the module imports the function
        import hypha_artifact.cli
        assert hasattr(hypha_artifact.cli, 'load_dotenv')


class TestArtifactCreation:
    """Test artifact instance creation."""

    @patch('hypha_artifact.cli.HyphaArtifact')
    def test_create_artifact_default_params(self, mock_artifact_class):
        """Test creating artifact with default parameters from environment."""
        with patch.dict(os.environ, {
            'HYPHA_SERVER_URL': 'https://test.hypha.io',
            'HYPHA_TOKEN': 'test-token',
            'HYPHA_WORKSPACE': 'test-workspace'
        }):
            create_artifact('test-artifact')
            
            mock_artifact_class.assert_called_once_with(
                'test-artifact',
                'test-workspace',
                'test-token',
                'https://test.hypha.io/public/services/artifact-manager'
            )

    @patch('hypha_artifact.cli.HyphaArtifact')
    def test_create_artifact_override_params(self, mock_artifact_class):
        """Test creating artifact with overridden parameters."""
        create_artifact(
            'test-artifact',
            workspace='custom-workspace',
            token='custom-token',
            server_url='https://custom.hypha.io'
        )
        
        mock_artifact_class.assert_called_once_with(
            'test-artifact',
            'custom-workspace',
            'custom-token',
            'https://custom.hypha.io/public/services/artifact-manager'
        )

    @patch('hypha_artifact.cli.HyphaArtifact')
    def test_create_artifact_server_url_trailing_slash(self, mock_artifact_class):
        """Test that trailing slashes are removed from server URLs."""
        create_artifact(
            'test-artifact',
            workspace='test-workspace',
            token='test-token',
            server_url='https://test.hypha.io/'
        )
        
        mock_artifact_class.assert_called_once_with(
            'test-artifact',
            'test-workspace',
            'test-token',
            'https://test.hypha.io/public/services/artifact-manager'
        )


class TestFormatting:
    """Test output formatting functions."""

    def test_format_file_listing_empty(self, capsys):
        """Test formatting empty file listing."""
        format_file_listing([])
        captured = capsys.readouterr()
        assert "📁 (empty)" in captured.out

    def test_format_file_listing_detailed_files(self, capsys):
        """Test formatting detailed file listing."""
        items = [
            {"name": "file1.txt", "type": "file", "size": 1024},
            {"name": "dir1", "type": "directory", "size": 0},
            {"name": "file2.py", "type": "file", "size": 2048}
        ]
        format_file_listing(items, detail=True)
        captured = capsys.readouterr()
        
        assert "📄 file1.txt (1,024 bytes)" in captured.out
        assert "📁 dir1" in captured.out
        assert "📄 file2.py (2,048 bytes)" in captured.out

    def test_format_file_listing_no_detail(self, capsys):
        """Test formatting file listing without details."""
        items = ["file1.txt", "dir1", "file2.py"]
        format_file_listing(items, detail=False)
        captured = capsys.readouterr()
        
        assert "📄 file1.txt" in captured.out
        assert "📄 dir1" in captured.out
        assert "📄 file2.py" in captured.out


class TestCommandParsing:
    """Test CLI argument parsing."""

    def test_main_no_arguments(self):
        """Test main function with no arguments shows help."""
        with patch('sys.argv', ['hypha-artifact']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2  # argparse exits with code 2 for missing required args

    def test_main_missing_artifact_id(self):
        """Test main function with missing artifact ID."""
        with patch('sys.argv', ['hypha-artifact', 'ls']):
            with pytest.raises(SystemExit):
                main()

    @patch('hypha_artifact.cli.cmd_ls')
    def test_main_ls_command(self, mock_cmd_ls):
        """Test main function with ls command."""
        with patch('sys.argv', ['hypha-artifact', '--artifact-id=test', 'ls', '/']):
            main()
            mock_cmd_ls.assert_called_once()

    @patch('hypha_artifact.cli.cmd_cat')
    def test_main_cat_command(self, mock_cmd_cat):
        """Test main function with cat command."""
        with patch('sys.argv', ['hypha-artifact', '--artifact-id=test', 'cat', '/file.txt']):
            main()
            mock_cmd_cat.assert_called_once()


class TestLsCommand:
    """Test ls command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    @patch('hypha_artifact.cli.format_file_listing')
    def test_cmd_ls_success(self, mock_format, mock_create_artifact):
        """Test successful ls command execution."""
        # Setup mock artifact
        mock_artifact = MagicMock()
        mock_artifact.ls.return_value = [{"name": "file1.txt", "type": "file"}]
        mock_create_artifact.return_value = mock_artifact
        
        # Create mock args
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/test',
            detail=True
        )
        
        cmd_ls(args)
        
        mock_artifact.ls.assert_called_once_with('/test', detail=True)
        mock_format.assert_called_once()

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_ls_error(self, mock_create_artifact):
        """Test ls command with error."""
        # Setup mock artifact to raise exception
        mock_artifact = MagicMock()
        mock_artifact.ls.side_effect = Exception("Test error")
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/test',
            detail=True
        )
        
        with pytest.raises(SystemExit):
            cmd_ls(args)


class TestCatCommand:
    """Test cat command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_cat_single_file(self, mock_create_artifact, capsys):
        """Test cat command with single file."""
        mock_artifact = MagicMock()
        mock_artifact.cat.return_value = "file content"
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/file.txt',
            paths=[],
            recursive=False
        )
        
        cmd_cat(args)
        
        mock_artifact.cat.assert_called_once_with('/file.txt', recursive=False)
        captured = capsys.readouterr()
        assert "file content" in captured.out

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_cat_multiple_files(self, mock_create_artifact, capsys):
        """Test cat command with multiple files."""
        mock_artifact = MagicMock()
        mock_artifact.cat.return_value = "file content"
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/file1.txt',
            paths=['/file2.txt', '/file3.txt'],
            recursive=False
        )
        
        cmd_cat(args)
        
        # Should be called 3 times (once for path, twice for paths)
        assert mock_artifact.cat.call_count == 3
        captured = capsys.readouterr()
        assert "==> /file1.txt <==" in captured.out
        assert "==> /file2.txt <==" in captured.out
        assert "==> /file3.txt <==" in captured.out


class TestCpCommand:
    """Test cp command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_cp_success(self, mock_create_artifact, capsys):
        """Test successful cp command execution."""
        mock_artifact = MagicMock()
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            source='/src.txt',
            destination='/dst.txt',
            recursive=False,
            maxdepth=None
        )
        
        cmd_cp(args)
        
        mock_artifact.copy.assert_called_once_with('/src.txt', '/dst.txt', recursive=False, maxdepth=None)
        captured = capsys.readouterr()
        assert "✅ Copied /src.txt to /dst.txt" in captured.out


class TestRmCommand:
    """Test rm command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_rm_success(self, mock_create_artifact, capsys):
        """Test successful rm command execution."""
        mock_artifact = MagicMock()
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            paths=['/file1.txt', '/file2.txt'],
            recursive=False
        )
        
        cmd_rm(args)
        
        # Should be called twice
        expected_calls = [call('/file1.txt', recursive=False), call('/file2.txt', recursive=False)]
        mock_artifact.rm.assert_has_calls(expected_calls)
        
        captured = capsys.readouterr()
        assert "✅ Removed /file1.txt" in captured.out
        assert "✅ Removed /file2.txt" in captured.out


class TestInfoCommand:
    """Test info command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_info_success(self, mock_create_artifact, capsys):
        """Test successful info command execution."""
        mock_artifact = MagicMock()
        mock_artifact.info.return_value = {"name": "file.txt", "size": 1024, "type": "file"}
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            paths=['/file.txt']
        )
        
        cmd_info(args)
        
        mock_artifact.info.assert_called_once_with('/file.txt')
        captured = capsys.readouterr()
        assert "📊 Information for /file.txt:" in captured.out
        assert '"name": "file.txt"' in captured.out


class TestUploadDownloadCommands:
    """Test upload and download command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    @patch('builtins.open', new_callable=mock_open, read_data=b"test content")
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    def test_cmd_upload_success(self, mock_is_file, mock_exists, mock_open_func, mock_create_artifact, capsys):
        """Test successful upload command execution."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_artifact = MagicMock()
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            local_path='local.txt',
            remote_path='/remote.txt',
            recursive=True,
            enable_multipart=False,
            multipart_threshold=100*1024*1024,
            chunk_size=10*1024*1024
        )
        
        cmd_upload(args)
        
        mock_artifact.upload.assert_called_once_with(
            'local.txt',
            '/remote.txt',
            recursive=True,
            enable_multipart=False,
            multipart_threshold=100*1024*1024,
            chunk_size=10*1024*1024
        )
        captured = capsys.readouterr()
        assert "✅ Uploaded file local.txt to /remote.txt" in captured.out

    @patch('hypha_artifact.cli.create_artifact')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    def test_cmd_upload_folder_success(self, mock_is_dir, mock_exists, mock_create_artifact, capsys):
        """Test successful upload command execution with folder."""
        mock_exists.return_value = True
        mock_is_dir.return_value = True
        mock_artifact = MagicMock()
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            local_path='./my-folder',
            remote_path='/remote-folder',
            recursive=True,
            enable_multipart=False,
            multipart_threshold=100*1024*1024,
            chunk_size=10*1024*1024
        )
        
        cmd_upload(args)
        
        mock_artifact.upload.assert_called_once_with(
            './my-folder',
            '/remote-folder',
            recursive=True,
            enable_multipart=False,
            multipart_threshold=100*1024*1024,
            chunk_size=10*1024*1024
        )
        captured = capsys.readouterr()
        assert "✅ Uploaded folder ./my-folder to /remote-folder" in captured.out

    @patch('hypha_artifact.cli.create_artifact')
    @patch('builtins.open', new_callable=mock_open)
    def test_cmd_download_success(self, mock_open_func, mock_create_artifact, capsys):
        """Test successful download command execution."""
        mock_artifact = MagicMock()
        mock_remote_file = MagicMock()
        mock_remote_file.read.return_value = b"remote content"
        mock_artifact.open.return_value.__enter__.return_value = mock_remote_file
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            remote_path='/remote.txt',
            local_path='local.txt'
        )
        
        cmd_download(args)
        
        mock_artifact.open.assert_called_once_with('/remote.txt', 'rb')
        captured = capsys.readouterr()
        assert "✅ Downloaded /remote.txt to local.txt" in captured.out


class TestSizeCommand:
    """Test size command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_size_single_file(self, mock_create_artifact, capsys):
        """Test size command with single file."""
        mock_artifact = MagicMock()
        mock_artifact.size.return_value = 1024
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            paths=['/file.txt']
        )
        
        cmd_size(args)
        
        mock_artifact.size.assert_called_once_with('/file.txt')
        captured = capsys.readouterr()
        assert "1,024 bytes" in captured.out

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_size_multiple_files(self, mock_create_artifact, capsys):
        """Test size command with multiple files."""
        mock_artifact = MagicMock()
        mock_artifact.sizes.return_value = [1024, 2048]
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            paths=['/file1.txt', '/file2.txt']
        )
        
        cmd_size(args)
        
        mock_artifact.sizes.assert_called_once_with(['/file1.txt', '/file2.txt'])
        captured = capsys.readouterr()
        assert "/file1.txt: 1,024 bytes" in captured.out
        assert "/file2.txt: 2,048 bytes" in captured.out


class TestExistsCommand:
    """Test exists command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_exists_success(self, mock_create_artifact, capsys):
        """Test exists command execution."""
        mock_artifact = MagicMock()
        mock_artifact.exists.side_effect = [True, False]  # First file exists, second doesn't
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            paths=['/existing.txt', '/missing.txt']
        )
        
        cmd_exists(args)
        
        expected_calls = [call('/existing.txt'), call('/missing.txt')]
        mock_artifact.exists.assert_has_calls(expected_calls)
        
        captured = capsys.readouterr()
        assert "/existing.txt: ✅ exists" in captured.out
        assert "/missing.txt: ❌ does not exist" in captured.out


class TestFindCommand:
    """Test find command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_find_simple(self, mock_create_artifact, capsys):
        """Test find command execution."""
        mock_artifact = MagicMock()
        mock_artifact.find.return_value = ['/file1.txt', '/dir1/file2.txt']
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/',
            maxdepth=None,
            include_dirs=False,
            detail=False
        )
        
        cmd_find(args)
        
        mock_artifact.find.assert_called_once_with('/', maxdepth=None, withdirs=False, detail=False)
        captured = capsys.readouterr()
        assert "/file1.txt" in captured.out
        assert "/dir1/file2.txt" in captured.out


class TestHeadCommand:
    """Test head command functionality."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_cmd_head_text_content(self, mock_create_artifact, capsys):
        """Test head command with text content."""
        mock_artifact = MagicMock()
        mock_artifact.head.return_value = b"Hello World\nThis is a test file"
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/file.txt',
            bytes=1024
        )
        
        cmd_head(args)
        
        mock_artifact.head.assert_called_once_with('/file.txt', size=1024)
        captured = capsys.readouterr()
        assert "Hello World" in captured.out


class TestErrorHandling:
    """Test error handling in CLI commands."""

    @patch('hypha_artifact.cli.create_artifact')
    def test_command_error_handling(self, mock_create_artifact):
        """Test that commands handle errors gracefully."""
        mock_artifact = MagicMock()
        mock_artifact.ls.side_effect = Exception("Network error")
        mock_create_artifact.return_value = mock_artifact
        
        args = argparse.Namespace(
            artifact_id='test-artifact',
            workspace=None,
            token=None,
            server_url=None,
            path='/',
            detail=True
        )
        
        with pytest.raises(SystemExit) as exc_info:
            cmd_ls(args)
        assert exc_info.value.code == 1


class TestIntegration:
    """Integration tests combining multiple CLI features."""

    @patch.dict(os.environ, {
        'HYPHA_SERVER_URL': 'https://test.hypha.io',
        'HYPHA_TOKEN': 'test-token',
        'HYPHA_WORKSPACE': 'test-workspace'
    })
    @patch('hypha_artifact.cli.cmd_ls')
    def test_full_command_pipeline(self, mock_cmd_ls):
        """Test full command execution pipeline."""
        with patch('sys.argv', ['hypha-artifact', '--artifact-id=test-artifact', 'ls', '/data']):
            main()
            mock_cmd_ls.assert_called_once()
            
            # Verify the arguments passed to the command
            call_args = mock_cmd_ls.call_args[0][0]
            assert call_args.artifact_id == 'test-artifact'
            assert call_args.path == '/data'

    def test_workspace_in_artifact_id(self):
        """Test handling workspace embedded in artifact ID."""
        with patch('hypha_artifact.cli.HyphaArtifact') as mock_artifact_class:
            create_artifact(
                'workspace/artifact-name',
                workspace='explicit-workspace',  # Provide explicit workspace
                token='test-token',
                server_url='https://test.hypha.io'
            )
            
            # Should use the provided workspace
            mock_artifact_class.assert_called_once_with(
                'workspace/artifact-name',
                'explicit-workspace',
                'test-token',
                'https://test.hypha.io/public/services/artifact-manager'
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 