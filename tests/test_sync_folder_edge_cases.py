"""Minimal integration tests for sync HyphaArtifact folder edge cases.

Focus on methods that may behave differently or fail when the path is a directory.
"""

from typing import Any, cast

import pytest

from hypha_artifact import HyphaArtifact


@pytest.fixture(scope="module", name="artifact")
def get_artifact(artifact_name: str, artifact_setup_teardown: tuple[str, str]) -> Any:
    token, workspace = artifact_setup_teardown
    return HyphaArtifact(
        artifact_name,
        workspace,
        token,
        server_url="https://hypha.aicell.io",
    )


class TestSyncFolderEdgeCases:
    def test_directory_methods(self, artifact: HyphaArtifact) -> None:
        folder = "edge_dir"
        subdir = f"{folder}/sub"
        file_path = f"{subdir}/a.txt"
        content = "folder-edge"

        # Create a directory and a file inside it
        artifact.edit(stage=True)
        artifact.makedirs(subdir, exist_ok=True)
        with artifact.open(file_path, "w") as f:
            f.write(content)
        artifact.commit()

        # exists/isdir/isfile on a directory
        assert artifact.exists(folder) is True
        assert artifact.isdir(folder) is True
        assert artifact.isfile(folder) is False

        # listdir/ls/info/size on a directory
        names = artifact.listdir(folder)
        assert "sub" in names

        ls_names = artifact.ls(folder, detail=False)
        assert "sub" in ls_names

        info = artifact.info(folder)
        assert info.get("type") == "directory"
        assert artifact.size(folder) == 0

        # find should include nested files when starting from folder
        files = artifact.find(folder)
        assert f"{subdir}/a.txt" in files

        # cat on a directory should work with recursive=True
        result = artifact.cat(folder, recursive=True)
        assert isinstance(result, dict)
        result_map = cast("dict[str, str | None]", result)
        assert file_path in result_map
        assert result_map[file_path] == content
