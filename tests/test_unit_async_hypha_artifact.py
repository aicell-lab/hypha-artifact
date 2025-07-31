# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Unit tests for the AsyncHyphaArtifact module."""


from unittest.mock import MagicMock, AsyncMock
import pytest
from pytest_mock import MockerFixture
from hypha_artifact import AsyncHyphaArtifact
from hypha_artifact.classes import ArtifactItem


@pytest.fixture(name="async_artifact")
def get_async_artifact(mocker: MockerFixture) -> AsyncHyphaArtifact:
    """Create a test artifact with a mocked async client."""
    mock_client = MagicMock()
    mock_client.request = AsyncMock()
    mocker.patch(
        "hypha_artifact.async_hypha_artifact.httpx.AsyncClient",
        return_value=mock_client,
    )
    artifact = AsyncHyphaArtifact("test-artifact", "test-workspace")
    artifact._client = mock_client
    return artifact


class TestAsyncHyphaArtifactUnit:
    """Unit test suite for the AsyncHyphaArtifact class."""

    @pytest.mark.asyncio
    async def test_edit(
        self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture
    ):
        """Test the edit method."""
        mock_remote_post = mocker.patch(
            "hypha_artifact.async_hypha_artifact._state.remote_post", new=AsyncMock()
        )
        await async_artifact.edit(stage=True)
        mock_remote_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit(
        self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture
    ):
        """Test the commit method."""
        mock_remote_post = mocker.patch(
            "hypha_artifact.async_hypha_artifact._state.remote_post", new=AsyncMock()
        )
        await async_artifact.commit()
        mock_remote_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cat(self, async_artifact: AsyncHyphaArtifact):
        """Test the cat method."""
        async_artifact.open = MagicMock()
        async_artifact.open.return_value.__aenter__.return_value.read = AsyncMock(
            return_value="test"
        )
        await async_artifact.cat("test.txt")
        async_artifact.open.assert_called_once_with("test.txt", "r")

    @pytest.mark.asyncio
    async def test_copy(
        self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture
    ):
        """Test the copy method."""
        mock_copy_single_file = mocker.patch(
            "hypha_artifact.async_hypha_artifact._io._copy_single_file",
            new=AsyncMock(),
        )
        await async_artifact.copy("a.txt", "b.txt")
        mock_copy_single_file.assert_called_once_with(async_artifact, "a.txt", "b.txt")

    @pytest.mark.asyncio
    async def test_rm(self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture):
        """Test the rm method."""
        mock_remote_post = mocker.patch(
            "hypha_artifact.async_hypha_artifact._remote.remote_post", new=AsyncMock()
        )
        await async_artifact.rm("test.txt")
        mock_remote_post.assert_called_once_with(
            async_artifact, "remove_file", {"file_path": "test.txt"}
        )

    @pytest.mark.asyncio
    async def test_exists(self, async_artifact: AsyncHyphaArtifact):
        """Test the exists method."""
        async_artifact.open = MagicMock()
        async_artifact.open.return_value.__aenter__.return_value.read = AsyncMock()
        await async_artifact.exists("test.txt")
        async_artifact.open.assert_called_with("test.txt", "r")

    @pytest.mark.asyncio
    async def test_ls(self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture):
        """Test the ls method."""
        mock_remote_list_contents = mocker.patch(
            "hypha_artifact.async_hypha_artifact._fs.remote_list_contents",
            new=AsyncMock(return_value=[]),
        )
        await async_artifact.ls("/")
        mock_remote_list_contents.assert_called_once_with(async_artifact, "/")

    @pytest.mark.asyncio
    async def test_info(self, async_artifact: AsyncHyphaArtifact):
        """Test the info method."""
        # Mock the ls method that info actually calls
        async_artifact.ls = AsyncMock(
            return_value=[
                ArtifactItem(name="test.txt", type="file", size=123, last_modified=None)
            ]
        )
        result = await async_artifact.info("test.txt")
        async_artifact.ls.assert_called_once_with(".", detail=True)
        assert result == ArtifactItem(
            name="test.txt", type="file", size=123, last_modified=None
        )

    @pytest.mark.asyncio
    async def test_info_root(self, async_artifact: AsyncHyphaArtifact):
        """Test the info method for the root directory."""
        async_artifact.ls = AsyncMock(return_value=[{"name": "test.txt"}])
        result = await async_artifact.info("/")
        assert result == {
            "name": "/",
            "type": "directory",
            "size": 0,
            "last_modified": None,
        }

    @pytest.mark.asyncio
    async def test_isdir(self, async_artifact: AsyncHyphaArtifact):
        """Test the isdir method."""
        async_artifact.info = AsyncMock(return_value={"type": "directory"})
        await async_artifact.isdir("test")
        async_artifact.info.assert_called_once_with("test")

    @pytest.mark.asyncio
    async def test_isfile(self, async_artifact: AsyncHyphaArtifact):
        """Test the isfile method."""
        async_artifact.info = AsyncMock(return_value={"type": "file"})
        await async_artifact.isfile("test.txt")
        async_artifact.info.assert_called_once_with("test.txt")

    @pytest.mark.asyncio
    async def test_find(self, async_artifact: AsyncHyphaArtifact):
        """Test the find method."""
        async_artifact.ls = AsyncMock(return_value=[])
        await async_artifact.find("/")
        async_artifact.ls.assert_called_once_with("/")
