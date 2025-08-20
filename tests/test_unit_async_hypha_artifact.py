# pylint: disable=protected-access
# pyright: reportPrivateUsage=false
"""Unit tests for the AsyncHyphaArtifact module."""


from unittest.mock import AsyncMock, MagicMock

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
    artifact = AsyncHyphaArtifact(
        "test-artifact",
        "test-workspace",
        server_url="https://hypha.aicell.io",
    )
    artifact._client = mock_client
    return artifact


class TestAsyncHyphaArtifactUnit:
    """Unit test suite for the AsyncHyphaArtifact class."""

    @pytest.mark.asyncio
    async def test_edit(
        self,
        async_artifact: AsyncHyphaArtifact,
        mocker: MockerFixture,
    ):
        """Test the edit method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post = AsyncMock(return_value=mock_response)
        mock_remote_post = mocker.patch.object(
            async_artifact._client,
            "post",
            new=mock_post,
        )
        await async_artifact.edit(stage=True)
        mock_remote_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_commit(
        self,
        async_artifact: AsyncHyphaArtifact,
        mocker: MockerFixture,
    ):
        """Test the commit method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post = AsyncMock(return_value=mock_response)
        mock_remote_post = mocker.patch.object(
            async_artifact._client,
            "post",
            new=mock_post,
        )
        await async_artifact.commit()
        mock_remote_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cat(self, async_artifact: AsyncHyphaArtifact):
        """Test the cat method."""
        async_artifact.open = MagicMock()
        async_artifact.open.return_value.__aenter__.return_value.read = AsyncMock(
            return_value="test",
        )
        await async_artifact.cat("test.txt")
        async_artifact.open.assert_called_once_with("test.txt", "r", version=None)

    @pytest.mark.asyncio
    async def test_copy(
        self,
        async_artifact: AsyncHyphaArtifact,
        mocker: MockerFixture,
    ):
        """Test the copy method."""
        async_artifact.open = MagicMock()
        async_artifact.open.return_value.__aenter__.return_value.read = AsyncMock()
        await async_artifact.copy("a.txt", "b.txt")
        async_artifact.open.assert_called_with("b.txt", "wb")

    @pytest.mark.asyncio
    async def test_rm(self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture):
        """Test the rm method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "{}"
        mock_post = AsyncMock(return_value=mock_response)
        mock_remote_post = mocker.patch.object(
            async_artifact._client,
            "post",
            new=mock_post,
        )
        mock_remote_get = mocker.patch.object(
            async_artifact._client,
            "get",
            new=mock_post,
        )
        await async_artifact.rm("test.txt")
        mock_remote_post.assert_called_with(
            headers={},
            json={"artifact_id": "test-artifact", "file_path": "test.txt"},
            url="https://hypha.aicell.io/public/services/artifact-manager/remove_file",
        )

        # url=get_method_url(self, ArtifactMethod.REMOVE_FILE),
        #     headers=get_headers(self),
        #     json=params,

    @pytest.mark.asyncio
    async def test_exists(self, async_artifact: AsyncHyphaArtifact):
        """Test the exists method."""
        async_artifact.open = MagicMock()
        async_artifact.open.return_value.__aenter__.return_value.read = AsyncMock()
        await async_artifact.exists("test.txt")
        async_artifact.open.assert_called_with("test.txt", "r", version=None)

    @pytest.mark.asyncio
    async def test_ls(self, async_artifact: AsyncHyphaArtifact, mocker: MockerFixture):
        """Test the ls method."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = "[]"
        mock_response.json = AsyncMock(return_value=[])
        mock_get = AsyncMock(return_value=mock_response)
        mock_remote_post = mocker.patch.object(
            async_artifact._client,
            "get",
            new=mock_get,
        )
        await async_artifact.ls("/", detail=True)
        mock_remote_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_info(self, async_artifact: AsyncHyphaArtifact):
        """Test the info method."""
        # Mock the ls method that info actually calls
        async_artifact.ls = AsyncMock(
            return_value=[
                ArtifactItem(
                    name="test.txt",
                    type="file",
                    size=123,
                    last_modified=None,
                ),
            ],
        )
        result = await async_artifact.info("test.txt")
        async_artifact.ls.assert_called_once_with(".", detail=True, version=None)
        assert result == ArtifactItem(
            name="test.txt",
            type="file",
            size=123,
            last_modified=None,
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
        async_artifact.info.assert_called_once_with("test", version=None)

    @pytest.mark.asyncio
    async def test_isfile(self, async_artifact: AsyncHyphaArtifact):
        """Test the isfile method."""
        async_artifact.info = AsyncMock(return_value={"type": "file"})
        await async_artifact.isfile("test.txt")
        async_artifact.info.assert_called_once_with("test.txt", version=None)

    @pytest.mark.asyncio
    async def test_find(self, async_artifact: AsyncHyphaArtifact):
        """Test the find method."""
        async_artifact.ls = AsyncMock(return_value=[])
        await async_artifact.find("/")
        async_artifact.ls.assert_called_once_with("/", detail=True, version=None)
