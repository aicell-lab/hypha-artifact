"""Hypha Artifact Command Line Interface"""

from collections.abc import Callable
import os
import sys
from typing import Any
import fire  # pyright: ignore
from dotenv import load_dotenv
from hypha_artifact.hypha_artifact import HyphaArtifact
from hypha_artifact.utils import OnError, ensure_dict

load_dotenv()


def get_connection_params() -> dict[str, str]:
    """Get connection parameters from environment variables."""
    env_names: list[str] = [
        "HYPHA_SERVER_URL",
        "HYPHA_TOKEN",
        "HYPHA_WORKSPACE",
    ]

    connection_params: dict[str, str] = {}
    for env_name in env_names:
        value = os.getenv(env_name)
        if not value:
            print(f"❌ Missing {env_name} environment variable", file=sys.stderr)
            sys.exit(1)
        connection_params[env_name] = value

    return connection_params


class ArtifactCLI(HyphaArtifact):
    """Command Line Interface for Hypha Artifact."""

    def __init__(
        self,
        artifact_id: str,
        workspace: str | None = None,
        token: str | None = None,
        server_url: str | None = None,
    ):
        """Initialize the CLI with HyphaArtifact parameters."""
        if not server_url or not workspace:
            connection_params = get_connection_params()
            server_url = connection_params["HYPHA_SERVER_URL"]
            token = connection_params["HYPHA_TOKEN"]
            workspace = connection_params["HYPHA_WORKSPACE"]

        if server_url.endswith("/"):
            server_url = server_url[:-1]

        super().__init__(
            artifact_id, workspace=workspace, token=token, server_url=server_url
        )

    def put(
        self,
        lpath: str | list[str],
        rpath: str | list[str],
        recursive: bool = False,
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        multipart_config: str | dict[str, Any] | None = None,
    ) -> None:
        multipart_config_dict = ensure_dict(multipart_config)

        super().put(
            lpath=lpath,
            rpath=rpath,
            recursive=recursive,
            callback=callback,
            maxdepth=maxdepth,
            on_error=on_error,
            multipart_config=multipart_config_dict,
        )

    def edit(
        self,
        manifest: str | dict[str, Any] | None = None,
        type: str | None = None,  # pylint: disable=redefined-builtin
        config: str | dict[str, Any] | None = None,
        secrets: str | dict[str, str] | None = None,
        version: str | None = None,
        comment: str | None = None,
        stage: bool = False,
    ) -> None:
        manifest_dict = ensure_dict(manifest)
        config_dict = ensure_dict(config)
        secrets_dict = ensure_dict(secrets)

        super().edit(
            manifest=manifest_dict,
            type=type,
            config=config_dict,
            secrets=secrets_dict,
            version=version,
            comment=comment,
            stage=stage,
        )


def main():
    """Main CLI entry point."""
    # TODO: hide open
    # TODO: add --stage option to all cli operations
    # TODO: fix "is folder" errors in get
    # TODO: try CLI methods in general
    # TODO: list children (artifacts)
    # TODO: automatically multipart if > ~100 MB
    fire.Fire(ArtifactCLI)  # pyright: ignore


if __name__ == "__main__":
    main()
