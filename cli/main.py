"""Hypha Artifact Command Line Interface"""

import os
import sys
import fire  # pyright: ignore
from dotenv import load_dotenv
from hypha_artifact.hypha_artifact import HyphaArtifact

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


def main():
    """Main CLI entry point."""
    fire.Fire(ArtifactCLI)  # pyright: ignore


if __name__ == "__main__":
    main()
