# pylint: disable=protected-access
"""Unit tests for AsyncArtifactHttpFile header forwarding."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hypha_artifact.async_artifact_file import AsyncArtifactHttpFile


@pytest.mark.asyncio
async def test_download_content_includes_additional_headers():
    """download_content should merge caller-provided headers into the GET request."""

    async def url_func() -> str:
        return "https://example.org/resource"

    file_obj = AsyncArtifactHttpFile(
        url_factory=url_func, additional_headers={"X-Test": "abc"}
    )

    # Resolve URL explicitly to avoid entering context (we mock the client)
    file_obj._url = await url_func()  # type: ignore[attr-defined]

    mock_client = AsyncMock()
    response = MagicMock()
    response.content = b"payload"
    response.raise_for_status = MagicMock()
    mock_client.get.return_value = response
    file_obj._client = mock_client  # type: ignore[attr-defined]

    await file_obj.download_content()

    mock_client.get.assert_awaited_once_with(
        "https://example.org/resource",
        headers={"Accept-Encoding": "identity", "X-Test": "abc"},
        timeout=60,
    )


@pytest.mark.asyncio
async def test_upload_content_includes_additional_headers():
    """upload_content should merge caller-provided headers into the PUT request."""

    async def url_func() -> str:
        return "https://example.org/resource"

    file_obj = AsyncArtifactHttpFile(
        mode="wb",
        content_type="text/plain",
        additional_headers={"X-Test": "abc"},
        url_factory=url_func,
    )

    # Resolve URL explicitly to avoid entering context (we mock the client)
    file_obj._url = await url_func()  # type: ignore[attr-defined]

    await file_obj.write(b"data")

    mock_client = AsyncMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    mock_client.put.return_value = response
    file_obj._client = mock_client  # type: ignore[attr-defined]

    await file_obj.upload_content()

    mock_client.put.assert_awaited_once_with(
        "https://example.org/resource",
        content=b"data",
        headers={
            "Content-Type": "text/plain",
            "Content-Length": "4",
            "X-Test": "abc",
        },
        timeout=120,
    )
