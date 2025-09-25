"""Hypha Artifact Command Line Interface."""

import json
import logging
import os
import shlex
import sys
from collections.abc import Callable
from typing import Any

import fire
from dotenv import load_dotenv

from hypha_artifact.classes import OnError
from hypha_artifact.hypha_artifact import HyphaArtifact

logger = logging.getLogger(__name__)


def ensure_dict(obj: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Ensure the given object is a dictionary.

    Parameters
    ----------
    obj: str | dict[str, Any] | None
        The object to check

    """
    if isinstance(obj, dict):
        return obj

    if isinstance(obj, str):
        return json.loads(obj)

    return None


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
            info_msg = f"Missing {env_name} environment variable"
            logger.error(info_msg)
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
    ) -> None:
        """Initialize the CLI with HyphaArtifact parameters."""
        if not server_url or not workspace:
            connection_params = get_connection_params()
            server_url = connection_params["HYPHA_SERVER_URL"]
            token = connection_params["HYPHA_TOKEN"]
            workspace = connection_params["HYPHA_WORKSPACE"]

        server_url = server_url.removesuffix("/")

        super().__init__(
            artifact_id,
            workspace=workspace,
            token=token,
            server_url=server_url,
        )

    def put(
        self,
        lpath: str | list[str],
        rpath: str | list[str],
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        multipart_config: str | dict[str, Any] | None = None,
        *,
        recursive: bool = False,
    ) -> None:
        """Upload files to the remote artifact.

        Args:
            lpath (str | list[str]): Local path(s) to upload
            rpath (str | list[str]): Remote path(s) to upload to
            callback (None | Callable[[dict[str, Any]], None], optional): Callback
                function to call on upload progress. Defaults to None.
            maxdepth (int | None, optional): Maximum depth to upload. Defaults to None.
            on_error (OnError, optional): Error handling strategy. Defaults to "raise".
            multipart_config (str | dict[str, Any] | None, optional): Multipart upload
                configuration. Defaults to None.
            recursive (bool, optional): Whether to upload directories recursively.
                Defaults to False.

        """
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

    def get(
        self,
        rpath: str | list[str],
        lpath: str | list[str],
        callback: None | Callable[[dict[str, Any]], None] = None,
        maxdepth: int | None = None,
        on_error: OnError = "raise",
        version: str | None = None,
        *,
        recursive: bool = False,
    ) -> None:
        """Download files from the remote artifact to local filesystem.

        Args:
            rpath (str | list[str]): Remote path(s) to download
            lpath (str | list[str]): Local destination path(s)
            callback (None | Callable[[dict[str, Any]], None], optional): Callback
                function to call on download progress. Defaults to None.
            maxdepth (int | None, optional): Maximum depth to download.
                Defaults to None.
            on_error (OnError, optional): Error handling strategy. Defaults to "raise".
            version (str | None, optional): Artifact version to download from.
                Defaults to None.
            recursive (bool, optional): Whether to download directories recursively.
                Defaults to False.

        """
        super().get(
            rpath=rpath,
            lpath=lpath,
            recursive=recursive,
            callback=callback,
            maxdepth=maxdepth,
            on_error=on_error,
            version=version,
        )

    def edit(
        self,
        manifest: str | dict[str, Any] | None = None,
        type: str | None = None,  # noqa: A002
        config: str | dict[str, Any] | None = None,
        secrets: str | dict[str, str] | None = None,
        version: str | None = None,
        comment: str | None = None,
        *,
        stage: bool = False,
    ) -> None:
        """Edit an existing artifact's manifest.

        Args:
            manifest (str | dict[str, Any] | None, optional): The updated manifest.
                Defaults to None.
            type (str | None, optional): The type of the artifact. Defaults to None.
            config (str | dict[str, Any] | None, optional):
                A dictionary containing additional configuration options for the
                artifact. Defaults to None.
            secrets (str | dict[str, str] | None, optional): A dictionary containing
                secrets to be stored with the artifact. Defaults to None.
            version (str | None, optional): Strict Validation Applied: Must be None,
                "new", or an existing version name from the artifact's versions array.
                Defaults to None.
            comment (str | None, optional): A comment to describe the changes made to
                the artifact. Defaults to None.
            stage (bool, optional): If True, the artifact will be edited in staging
                mode regardless of the version parameter. Defaults to False.

        """
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

    def run_shell(self, artifact_id: str) -> None:
        """Interactive mode."""
        initial_msg = (
            f"Welcome to the hypha-artifact shell for artifact '{artifact_id}'!"
            " Type 'exit' or Ctrl+C to quit."
            " For help, type '--help'"
        )
        print(initial_msg)  # noqa: T201
        while True:
            try:
                cmd = input("> ").strip()
                if cmd.lower() in ("exit", "quit"):
                    print("Exiting shell.")  # noqa: T201
                    break
                if not cmd:
                    continue

                args = shlex.split(cmd)

                fire.Fire(ArtifactCLI(artifact_id), args)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting shell.")  # noqa: T201
                break

    # Hide some methods from CLI
    def __dir__(self) -> list[str]:
        """Get a list of public methods in the CLI.

        Returns:
            list[str]: A list of public method names.

        """
        method_names = super().__dir__()
        hidden_names = ["open"]

        return [
            method_name
            for method_name in method_names
            if method_name not in hidden_names
        ]


def main() -> None:
    """Run main CLI entry point."""
    repl_num_args = 3
    if len(sys.argv) == repl_num_args and sys.argv[1] == "--artifact_id":
        artifact_id = sys.argv[2]
        ArtifactCLI(artifact_id).run_shell(artifact_id)
    else:
        fire.Fire(ArtifactCLI)


if __name__ == "__main__":
    main()
