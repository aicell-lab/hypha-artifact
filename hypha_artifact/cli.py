#!/usr/bin/env python3
"""
Hypha Artifact CLI - Command line interface for managing Hypha artifacts.

This CLI provides access to all artifact operations including file management,
directory operations, and metadata handling.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv, find_dotenv
import yaml

from hypha_artifact.hypha_artifact import HyphaArtifact
from hypha_artifact.async_hypha_artifact import AsyncHyphaArtifact

# Load environment variables
load_dotenv(dotenv_path=find_dotenv(usecwd=True))


def load_file_content(file_path: str) -> Dict[str, Any]:
    """Load content from JSON or YAML file."""
    if not file_path:
        return {}

    path = Path(file_path)
    if not path.exists():
        print(f"❌ File does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to determine format from extension
        if path.suffix.lower() in [".yaml", ".yml"]:
            if yaml is None:
                print(
                    "❌ YAML support not available. Please install PyYAML: pip install PyYAML",
                    file=sys.stderr,
                )
                sys.exit(1)
            return yaml.safe_load(content)
        elif path.suffix.lower() == ".json":
            return json.loads(content)
        else:
            # Try JSON first, then YAML
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                if yaml is not None:
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        pass
                print(
                    f"❌ Could not parse file as JSON or YAML: {file_path}",
                    file=sys.stderr,
                )
                sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def suggest_staging_command(operation: str) -> str:
    """Suggest the appropriate staging command for an operation."""
    return f"""
💡 This operation requires the artifact to be in staging mode.
   You can either:
   1. Put the artifact in staging mode first:
      hypha-artifact --artifact-id=your-artifact edit --stage
   2. Then retry your {operation} command
   
   Or use the Python API which handles staging automatically:
   artifact.{operation}(...)
"""


def get_connection_params() -> tuple[str, str, str]:
    """Get connection parameters from environment variables."""
    server_url = os.getenv("HYPHA_SERVER_URL")
    token = os.getenv("HYPHA_TOKEN")
    workspace = os.getenv("HYPHA_WORKSPACE")

    if not server_url:
        print("❌ Missing HYPHA_SERVER_URL environment variable", file=sys.stderr)
        sys.exit(1)

    if not token:
        print("❌ Missing HYPHA_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    if not workspace:
        print("❌ Missing HYPHA_WORKSPACE environment variable", file=sys.stderr)
        sys.exit(1)

    return server_url, token, workspace


def create_artifact(
    artifact_id: str,
    workspace: str | None = None,
    token: str | None = None,
    server_url: str | None = None,
) -> HyphaArtifact:
    """Create a HyphaArtifact instance with connection parameters."""
    if not server_url or not workspace:
        server_url, token, workspace = get_connection_params()

    # Convert server URL to artifact manager service URL
    if server_url.endswith("/"):
        server_url = server_url[:-1]
    service_url = f"{server_url}/public/services/artifact-manager"

    return HyphaArtifact(artifact_id, workspace, token, service_url)


async def create_async_artifact(
    artifact_id: str,
    workspace: str | None = None,
    token: str | None = None,
    server_url: str | None = None,
) -> AsyncHyphaArtifact:
    """Create an AsyncHyphaArtifact instance with connection parameters."""
    if not server_url or not workspace:
        server_url, token, workspace = get_connection_params()

    # Convert server URL to artifact manager service URL
    if server_url.endswith("/"):
        server_url = server_url[:-1]
    service_url = f"{server_url}/public/services/artifact-manager"

    return AsyncHyphaArtifact(artifact_id, workspace, token, service_url)


def format_file_listing(items: list, detail: bool = True) -> None:
    """Format and print file listing."""
    if not items:
        print("📁 (empty)")
        return

    for item in items:
        if isinstance(item, dict):
            file_type = item.get("type", "unknown")
            name = item.get("name", "")
            size = item.get("size", 0)

            if file_type == "directory":
                emoji = "📁"
                size_str = ""
            else:
                emoji = "📄"
                size_str = f" ({size:,} bytes)" if size else ""

            if detail:
                print(f"{emoji} {name}{size_str}")
            else:
                print(name)
        else:
            print(f"📄 {item}")


# Command implementations


def cmd_edit(args) -> None:
    """Edit artifact manifest, config, or stage the artifact."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Load manifest and config from files if provided
        manifest = load_file_content(args.manifest) if args.manifest else None
        config = load_file_content(args.config) if args.config else None

        # Prepare edit arguments
        edit_kwargs = {}
        if manifest:
            edit_kwargs["manifest"] = manifest
        if config:
            edit_kwargs["config"] = config
        if args.version:
            edit_kwargs["version"] = args.version
        if args.stage:
            edit_kwargs["stage"] = True
        if args.comment:
            edit_kwargs["comment"] = args.comment

        # Perform edit
        if edit_kwargs:
            artifact._remote_edit(**edit_kwargs)

            # Print what was done
            actions = []
            if manifest:
                actions.append("manifest updated")
            if config:
                actions.append("config updated")
            if args.stage:
                actions.append("artifact staged")
            if args.version and args.version != "stage":
                actions.append(f"version set to {args.version}")

            print(f"✅ Artifact edited: {', '.join(actions)}")
        else:
            print(
                "❌ No changes specified. Use --manifest, --config, --version, or --stage",
                file=sys.stderr,
            )
            sys.exit(1)

    except Exception as e:
        error_str = str(e)
        if "staging" in error_str.lower() or "stage" in error_str.lower():
            print(f"❌ Error editing artifact: {e}", file=sys.stderr)
            print(
                "💡 The artifact may already be in staging mode or require different staging options",
                file=sys.stderr,
            )
        else:
            print(f"❌ Error editing artifact: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_commit(args) -> None:
    """Commit staged changes to the artifact."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Prepare commit arguments
        commit_kwargs = {}
        if args.version:
            commit_kwargs["version"] = args.version
        if args.comment:
            commit_kwargs["comment"] = args.comment

        # Perform commit
        result = artifact._remote_commit(**commit_kwargs)

        if args.version:
            print(f"✅ Artifact committed as version {args.version}")
        else:
            print("✅ Artifact committed successfully")

    except Exception as e:
        error_str = str(e)
        if "staging" in error_str.lower() or "stage" in error_str.lower():
            print(f"❌ Error committing artifact: {e}", file=sys.stderr)
            print(
                "💡 The artifact may not be in staging mode. Use 'edit --stage' first.",
                file=sys.stderr,
            )
        else:
            print(f"❌ Error committing artifact: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_discard(args) -> None:
    """Discard staged changes to the artifact."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Perform discard
        result = artifact._remote_discard()
        print("✅ Staged changes discarded successfully")

    except Exception as e:
        error_str = str(e)
        if "staging" in error_str.lower() or "stage" in error_str.lower():
            print(f"❌ Error discarding changes: {e}", file=sys.stderr)
            print(
                "💡 The artifact may not have any staged changes to discard.",
                file=sys.stderr,
            )
        else:
            print(f"❌ Error discarding changes: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ls(args) -> None:
    """List files and directories in artifact."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Use stage parameter if provided
        kwargs = {"detail": args.detail}
        if hasattr(args, "stage") and args.stage:
            kwargs["version"] = "stage"

        items = artifact.ls(args.path, **kwargs)
        format_file_listing(items, args.detail)
    except Exception as e:
        print(f"❌ Error listing {args.path}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cat(args) -> None:
    """Display file contents."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Prepare kwargs for version/stage support
        kwargs = {"recursive": args.recursive}
        if hasattr(args, "stage") and args.stage:
            kwargs["version"] = "stage"

        if args.paths:
            # Multiple files - process main path plus additional paths
            all_paths = [args.path] + args.paths
            for path in all_paths:
                if len(all_paths) > 1:
                    print(f"\n==> {path} <==")
                content = artifact.cat(path, **kwargs)
                if content is not None:
                    print(content)
        else:
            # Single file
            content = artifact.cat(args.path, **kwargs)
            if content is not None:
                print(content)
    except Exception as e:
        print(f"❌ Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cp(args) -> None:
    """Copy files or directories."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Check if source exists before attempting copy
        if not artifact.exists(args.source):
            print(f"❌ Source file does not exist: {args.source}", file=sys.stderr)
            sys.exit(1)

        artifact.copy(
            args.source,
            args.destination,
            recursive=args.recursive,
            maxdepth=args.maxdepth,
        )
        print(f"✅ Copied {args.source} to {args.destination}")
    except Exception as e:
        error_str = str(e)
        if "staging" in error_str.lower() or "edit" in error_str.lower():
            print(f"❌ Error copying: {e}", file=sys.stderr)
            print(suggest_staging_command("copy"), file=sys.stderr)
        elif "500 Server Error" in error_str and "commit" in error_str:
            # This is likely a commit error - check if copy actually worked
            try:
                if artifact.exists(args.destination):
                    print(f"✅ Copied {args.source} to {args.destination}")
                    print(f"⚠️  Note: Copy succeeded but commit failed: {e}")
                    print(
                        "The copied file is available for use even without explicit commit."
                    )
                    return
            except:
                pass  # If exists check fails, fall through to error handling
            print(f"❌ Error copying: {e}", file=sys.stderr)
        else:
            print(f"❌ Error copying: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_rm(args) -> None:
    """Remove files or directories."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        for path in args.paths:
            # Check if file exists before attempting removal
            if not artifact.exists(path):
                print(f"❌ File does not exist: {path}", file=sys.stderr)
                continue

            try:
                artifact.rm(path, recursive=args.recursive)
                print(f"✅ Removed {path}")
            except Exception as e:
                error_str = str(e)
                if "staging" in error_str.lower() or "edit" in error_str.lower():
                    print(f"❌ Error removing {path}: {e}", file=sys.stderr)
                    print(suggest_staging_command("rm"), file=sys.stderr)
                elif "500 Server Error" in error_str and "commit" in error_str:
                    # This is likely a commit error - check if removal actually worked
                    try:
                        if not artifact.exists(path):
                            print(f"✅ Removed {path}")
                            print(f"⚠️  Note: Removal succeeded but commit failed: {e}")
                            print(
                                "The file has been removed even without explicit commit."
                            )
                            continue
                    except:
                        pass  # If exists check fails, fall through to error handling
                    print(f"❌ Error removing {path}: {e}", file=sys.stderr)
                else:
                    print(f"❌ Error removing {path}: {e}", file=sys.stderr)

    except Exception as e:
        print(f"❌ Error in remove operation: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_mkdir(args) -> None:
    """Create directories."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        for path in args.paths:
            artifact.mkdir(path, create_parents=args.parents)
            print(f"✅ Created directory {path}")
    except Exception as e:
        print(f"❌ Error creating directory: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args) -> None:
    """Show file or directory information."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        for path in args.paths:
            info = artifact.info(path)
            print(f"\n📊 Information for {path}:")
            print(json.dumps(info, indent=2))
    except Exception as e:
        print(f"❌ Error getting info: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_find(args) -> None:
    """Find files recursively."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        results = artifact.find(
            args.path,
            maxdepth=args.maxdepth,
            withdirs=args.include_dirs,
            detail=args.detail,
        )

        if args.detail and isinstance(results, dict):
            for path, info in results.items():
                file_type = info.get("type", "file")
                emoji = "📁" if file_type == "directory" else "📄"
                size = info.get("size", 0)
                size_str = f" ({size:,} bytes)" if size and file_type == "file" else ""
                print(f"{emoji} {path}{size_str}")
        else:
            for path in results:
                print(path)
    except Exception as e:
        print(f"❌ Error finding files: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_head(args) -> None:
    """Show first bytes of file."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        # Prepare kwargs for version/stage support
        kwargs = {"size": args.bytes}
        if hasattr(args, "stage") and args.stage:
            kwargs["version"] = "stage"

        content = artifact.head(args.path, **kwargs)
        # Handle both text and binary content
        try:
            print(content.decode("utf-8"))
        except UnicodeDecodeError:
            print(f"Binary content ({len(content)} bytes):")
            print(content.hex())
    except Exception as e:
        print(f"❌ Error reading file head: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_size(args) -> None:
    """Show file sizes."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        if len(args.paths) == 1:
            size = artifact.size(args.paths[0])
            print(f"{size:,} bytes")
        else:
            sizes = artifact.sizes(args.paths)
            for path, size in zip(args.paths, sizes):
                print(f"{path}: {size:,} bytes")
    except Exception as e:
        print(f"❌ Error getting file size: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_exists(args) -> None:
    """Check if path exists."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        for path in args.paths:
            exists = artifact.exists(path)
            status = "✅ exists" if exists else "❌ does not exist"
            print(f"{path}: {status}")
    except Exception as e:
        print(f"❌ Error checking existence: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_upload(args) -> None:
    """Upload a local file or folder to artifact."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        local_path = Path(args.local_path)
        if not local_path.exists():
            print(f"❌ Local path does not exist: {args.local_path}", file=sys.stderr)
            sys.exit(1)

        remote_path = args.remote_path or local_path.name

        # Use the Python API which handles staging automatically
        artifact.upload(
            local_path=local_path,
            remote_path=remote_path,
            recursive=args.recursive,
            enable_multipart=args.enable_multipart,
            multipart_threshold=args.multipart_threshold,
            chunk_size=args.chunk_size,
        )

        if local_path.is_file():
            print(f"✅ Uploaded file {args.local_path} to {remote_path}")
        else:
            print(f"✅ Uploaded directory {args.local_path} to {remote_path}")

    except Exception as e:
        error_str = str(e)
        if "staging" in error_str.lower() or "edit" in error_str.lower():
            print(f"❌ Error uploading: {e}", file=sys.stderr)
            print(suggest_staging_command("upload"), file=sys.stderr)
        else:
            print(f"❌ Error uploading: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_download(args) -> None:
    """Download a file from artifact to local filesystem."""
    artifact = create_artifact(
        args.artifact_id, args.workspace, args.token, args.server_url
    )

    try:
        local_path = (
            Path(args.local_path) if args.local_path else Path(args.remote_path).name
        )

        with artifact.open(args.remote_path, "rb") as remote_file:
            with open(local_path, "wb") as local_file:
                content = remote_file.read()
                local_file.write(content)
                print(f"✅ Downloaded {args.remote_path} to {local_path}")
    except Exception as e:
        print(f"❌ Error downloading file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Hypha Artifact CLI - Manage files and directories in Hypha artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hypha-artifact --artifact-id=my-artifact ls /
  hypha-artifact --artifact-id=my-artifact cat /data.txt
  hypha-artifact --artifact-id=my-artifact cp /src.txt /dst.txt
  hypha-artifact --artifact-id=my-artifact upload local.txt /remote.txt
  hypha-artifact --artifact-id=my-artifact upload --enable-multipart large-file.zip /data/
  hypha-artifact --artifact-id=my-artifact upload ./my-project /projects/my-project
        """,
    )

    # Global arguments
    parser.add_argument(
        "--artifact-id",
        required=True,
        help="Artifact ID (can include workspace: workspace/artifact)",
    )
    parser.add_argument("--workspace", help="Workspace name (overrides environment)")
    parser.add_argument("--token", help="Authentication token (overrides environment)")
    parser.add_argument("--server-url", help="Server URL (overrides environment)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ls command
    ls_parser = subparsers.add_parser("ls", help="List files and directories")
    ls_parser.add_argument(
        "path", nargs="?", default="/", help="Path to list (default: /)"
    )
    ls_parser.add_argument(
        "--detail", action="store_true", default=True, help="Show detailed information"
    )
    ls_parser.add_argument(
        "--no-detail", dest="detail", action="store_false", help="Show names only"
    )
    ls_parser.add_argument(
        "--stage", action="store_true", help="List files from staged version"
    )
    ls_parser.set_defaults(func=cmd_ls)

    # cat command
    cat_parser = subparsers.add_parser("cat", help="Display file contents")
    cat_parser.add_argument("path", help="File path to display")
    cat_parser.add_argument("paths", nargs="*", help="Additional file paths")
    cat_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively cat directory contents",
    )
    cat_parser.add_argument(
        "--stage", action="store_true", help="Read file from staged version"
    )
    cat_parser.set_defaults(func=cmd_cat)

    # cp command
    cp_parser = subparsers.add_parser("cp", help="Copy files or directories")
    cp_parser.add_argument("source", help="Source path")
    cp_parser.add_argument("destination", help="Destination path")
    cp_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Copy directories recursively"
    )
    cp_parser.add_argument("--maxdepth", type=int, help="Maximum recursion depth")
    cp_parser.set_defaults(func=cmd_cp)

    # rm command
    rm_parser = subparsers.add_parser("rm", help="Remove files or directories")
    rm_parser.add_argument("paths", nargs="+", help="Paths to remove")
    rm_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Remove directories recursively"
    )
    rm_parser.set_defaults(func=cmd_rm)

    # mkdir command
    mkdir_parser = subparsers.add_parser("mkdir", help="Create directories")
    mkdir_parser.add_argument("paths", nargs="+", help="Directory paths to create")
    mkdir_parser.add_argument(
        "-p",
        "--parents",
        action="store_true",
        default=True,
        help="Create parent directories",
    )
    mkdir_parser.set_defaults(func=cmd_mkdir)

    # info command
    info_parser = subparsers.add_parser(
        "info", help="Show file or directory information"
    )
    info_parser.add_argument("paths", nargs="+", help="Paths to get info for")
    info_parser.set_defaults(func=cmd_info)

    # find command
    find_parser = subparsers.add_parser("find", help="Find files recursively")
    find_parser.add_argument(
        "path", nargs="?", default="/", help="Base path to search from"
    )
    find_parser.add_argument("--maxdepth", type=int, help="Maximum recursion depth")
    find_parser.add_argument(
        "--include-dirs", action="store_true", help="Include directories in results"
    )
    find_parser.add_argument(
        "--detail", action="store_true", help="Show detailed information"
    )
    find_parser.set_defaults(func=cmd_find)

    # head command
    head_parser = subparsers.add_parser("head", help="Show first bytes of file")
    head_parser.add_argument("path", help="File path")
    head_parser.add_argument(
        "-n", "--bytes", type=int, default=1024, help="Number of bytes to show"
    )
    head_parser.add_argument(
        "--stage", action="store_true", help="Read file from staged version"
    )
    head_parser.set_defaults(func=cmd_head)

    # size command
    size_parser = subparsers.add_parser("size", help="Show file sizes")
    size_parser.add_argument("paths", nargs="+", help="File paths")
    size_parser.set_defaults(func=cmd_size)

    # exists command
    exists_parser = subparsers.add_parser("exists", help="Check if paths exist")
    exists_parser.add_argument("paths", nargs="+", help="Paths to check")
    exists_parser.set_defaults(func=cmd_exists)

    # edit command
    edit_parser = subparsers.add_parser(
        "edit", help="Edit artifact manifest, config, or put in staging mode"
    )
    edit_parser.add_argument("--manifest", help="Path to manifest YAML/JSON file")
    edit_parser.add_argument("--config", help="Path to config YAML/JSON file")
    edit_parser.add_argument(
        "--version", help="Version to edit or 'new' to create new version"
    )
    edit_parser.add_argument(
        "--stage", action="store_true", help="Put artifact in staging mode"
    )
    edit_parser.add_argument("--comment", help="Comment describing the changes")
    edit_parser.set_defaults(func=cmd_edit)

    # commit command
    commit_parser = subparsers.add_parser("commit", help="Commit staged changes")
    commit_parser.add_argument("--version", help="Custom version name for the commit")
    commit_parser.add_argument("--comment", help="Comment describing the commit")
    commit_parser.set_defaults(func=cmd_commit)

    # discard command
    discard_parser = subparsers.add_parser("discard", help="Discard staged changes")
    discard_parser.set_defaults(func=cmd_discard)

    # upload command
    upload_parser = subparsers.add_parser(
        "upload", help="Upload local file or folder to artifact"
    )
    upload_parser.add_argument("local_path", help="Local file or folder path")
    upload_parser.add_argument(
        "remote_path", nargs="?", help="Remote path in artifact (default: same name)"
    )
    upload_parser.add_argument(
        "--recursive",
        action="store_true",
        default=True,
        help="Upload subdirectories recursively when uploading folders (default: true)",
    )
    upload_parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Don't upload subdirectories",
    )
    upload_parser.add_argument(
        "--enable-multipart", action="store_true", help="Force multipart upload"
    )
    upload_parser.add_argument(
        "--multipart-threshold",
        type=int,
        default=100 * 1024 * 1024,
        help="File size threshold for multipart upload (bytes, default: 100MB)",
    )
    upload_parser.add_argument(
        "--chunk-size",
        type=int,
        default=10 * 1024 * 1024,
        help="Chunk size for multipart upload (bytes, default: 10MB)",
    )
    upload_parser.set_defaults(func=cmd_upload)

    # download command
    download_parser = subparsers.add_parser(
        "download", help="Download file from artifact"
    )
    download_parser.add_argument("remote_path", help="Remote file path in artifact")
    download_parser.add_argument(
        "local_path", nargs="?", help="Local file path (default: same name)"
    )
    download_parser.set_defaults(func=cmd_download)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main()
