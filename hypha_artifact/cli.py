#!/usr/bin/env python3
"""
Hypha Artifact CLI - Command line interface for managing Hypha artifacts.

This CLI provides access to all artifact operations including file management,
directory operations, and metadata handling.
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv, find_dotenv

from hypha_artifact.hypha_artifact import HyphaArtifact
from hypha_artifact.async_hypha_artifact import AsyncHyphaArtifact

# Load environment variables
load_dotenv(dotenv_path=find_dotenv(usecwd=True))


def get_connection_params() -> tuple[str, str, str]:
    """Get connection parameters from environment variables."""
    server_url = os.getenv("HYPHA_SERVER_URL")
    token = os.getenv("HYPHA_TOKEN") 
    workspace = os.getenv("HYPHA_WORKSPACE")
    
    if not server_url:
        print("❌ Missing HYPHA_SERVER_URL environment variable", file=sys.stderr)
        sys.exit(1)
        
    if not workspace:
        print("❌ Missing HYPHA_WORKSPACE environment variable", file=sys.stderr)
        sys.exit(1)
        
    return server_url, token, workspace


def create_artifact(artifact_id: str, workspace: str = None, token: str = None, server_url: str = None) -> HyphaArtifact:
    """Create a HyphaArtifact instance with connection parameters."""
    if not server_url or not workspace:
        server_url, token, workspace = get_connection_params()
    
    # Convert server URL to artifact manager service URL
    if server_url.endswith('/'):
        server_url = server_url[:-1]
    service_url = f"{server_url}/public/services/artifact-manager"
    
    return HyphaArtifact(artifact_id, workspace, token, service_url)


async def create_async_artifact(artifact_id: str, workspace: str = None, token: str = None, server_url: str = None) -> AsyncHyphaArtifact:
    """Create an AsyncHyphaArtifact instance with connection parameters."""
    if not server_url or not workspace:
        server_url, token, workspace = get_connection_params()
    
    # Convert server URL to artifact manager service URL  
    if server_url.endswith('/'):
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
def cmd_ls(args) -> None:
    """List files and directories in artifact."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        items = artifact.ls(args.path, detail=args.detail)
        format_file_listing(items, args.detail)
    except Exception as e:
        print(f"❌ Error listing {args.path}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cat(args) -> None:
    """Display file contents."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        if args.paths:
            # Multiple files - process main path plus additional paths
            all_paths = [args.path] + args.paths
            for path in all_paths:
                if len(all_paths) > 1:
                    print(f"\n==> {path} <==")
                content = artifact.cat(path, recursive=args.recursive)
                if content is not None:
                    print(content)
        else:
            # Single file
            content = artifact.cat(args.path, recursive=args.recursive)
            if content is not None:
                print(content)
    except Exception as e:
        print(f"❌ Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cp(args) -> None:
    """Copy files or directories."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        artifact.copy(args.source, args.destination, recursive=args.recursive, maxdepth=args.maxdepth)
        print(f"✅ Copied {args.source} to {args.destination}")
    except Exception as e:
        print(f"❌ Error copying: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_rm(args) -> None:
    """Remove files or directories."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        for path in args.paths:
            artifact.rm(path, recursive=args.recursive)
            print(f"✅ Removed {path}")
    except Exception as e:
        print(f"❌ Error removing: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_mkdir(args) -> None:
    """Create directories."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        for path in args.paths:
            artifact.mkdir(path, create_parents=args.parents)
            print(f"✅ Created directory {path}")
    except Exception as e:
        print(f"❌ Error creating directory: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args) -> None:
    """Show file or directory information."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
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
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        results = artifact.find(
            args.path, 
            maxdepth=args.maxdepth, 
            withdirs=args.include_dirs,
            detail=args.detail
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
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        content = artifact.head(args.path, size=args.bytes)
        # Handle both text and binary content
        try:
            print(content.decode('utf-8'))
        except UnicodeDecodeError:
            print(f"Binary content ({len(content)} bytes):")
            print(content.hex())
    except Exception as e:
        print(f"❌ Error reading file head: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_size(args) -> None:
    """Show file sizes."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
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
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
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
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        local_path = Path(args.local_path)
        if not local_path.exists():
            print(f"❌ Local path does not exist: {args.local_path}", file=sys.stderr)
            sys.exit(1)
            
        remote_path = args.remote_path or local_path.name
        
        # Use unified upload method
        artifact.upload(
            args.local_path,
            remote_path,
            recursive=args.recursive,
            enable_multipart=args.enable_multipart,
            multipart_threshold=args.multipart_threshold,
            chunk_size=args.chunk_size,
        )
        
        if local_path.is_file():
            print(f"✅ Uploaded file {args.local_path} to {remote_path}")
        else:
            print(f"✅ Uploaded folder {args.local_path} to {remote_path}")
    except Exception as e:
        print(f"❌ Error uploading: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_download(args) -> None:
    """Download a file from artifact to local filesystem."""
    artifact = create_artifact(args.artifact_id, args.workspace, args.token, args.server_url)
    
    try:
        local_path = Path(args.local_path) if args.local_path else Path(args.remote_path).name
        
        with artifact.open(args.remote_path, 'rb') as remote_file:
            with open(local_path, 'wb') as local_file:
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
        """
    )
    
    # Global arguments
    parser.add_argument("--artifact-id", required=True, help="Artifact ID (can include workspace: workspace/artifact)")
    parser.add_argument("--workspace", help="Workspace name (overrides environment)")
    parser.add_argument("--token", help="Authentication token (overrides environment)")  
    parser.add_argument("--server-url", help="Server URL (overrides environment)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ls command
    ls_parser = subparsers.add_parser("ls", help="List files and directories")
    ls_parser.add_argument("path", nargs="?", default="/", help="Path to list (default: /)")
    ls_parser.add_argument("--detail", action="store_true", default=True, help="Show detailed information")
    ls_parser.add_argument("--no-detail", dest="detail", action="store_false", help="Show names only")
    ls_parser.set_defaults(func=cmd_ls)
    
    # cat command
    cat_parser = subparsers.add_parser("cat", help="Display file contents")
    cat_parser.add_argument("path", help="File path to display")
    cat_parser.add_argument("paths", nargs="*", help="Additional file paths")
    cat_parser.add_argument("-r", "--recursive", action="store_true", help="Recursively cat directory contents")
    cat_parser.set_defaults(func=cmd_cat)
    
    # cp command
    cp_parser = subparsers.add_parser("cp", help="Copy files or directories") 
    cp_parser.add_argument("source", help="Source path")
    cp_parser.add_argument("destination", help="Destination path")
    cp_parser.add_argument("-r", "--recursive", action="store_true", help="Copy directories recursively")
    cp_parser.add_argument("--maxdepth", type=int, help="Maximum recursion depth")
    cp_parser.set_defaults(func=cmd_cp)
    
    # rm command
    rm_parser = subparsers.add_parser("rm", help="Remove files or directories")
    rm_parser.add_argument("paths", nargs="+", help="Paths to remove")
    rm_parser.add_argument("-r", "--recursive", action="store_true", help="Remove directories recursively")
    rm_parser.set_defaults(func=cmd_rm)
    
    # mkdir command
    mkdir_parser = subparsers.add_parser("mkdir", help="Create directories")
    mkdir_parser.add_argument("paths", nargs="+", help="Directory paths to create")
    mkdir_parser.add_argument("-p", "--parents", action="store_true", default=True, help="Create parent directories")
    mkdir_parser.set_defaults(func=cmd_mkdir)
    
    # info command
    info_parser = subparsers.add_parser("info", help="Show file or directory information")
    info_parser.add_argument("paths", nargs="+", help="Paths to get info for")
    info_parser.set_defaults(func=cmd_info)
    
    # find command
    find_parser = subparsers.add_parser("find", help="Find files recursively")
    find_parser.add_argument("path", nargs="?", default="/", help="Base path to search from")
    find_parser.add_argument("--maxdepth", type=int, help="Maximum recursion depth")
    find_parser.add_argument("--include-dirs", action="store_true", help="Include directories in results")
    find_parser.add_argument("--detail", action="store_true", help="Show detailed information")
    find_parser.set_defaults(func=cmd_find)
    
    # head command
    head_parser = subparsers.add_parser("head", help="Show first bytes of file")
    head_parser.add_argument("path", help="File path")
    head_parser.add_argument("-n", "--bytes", type=int, default=1024, help="Number of bytes to show")
    head_parser.set_defaults(func=cmd_head)
    
    # size command
    size_parser = subparsers.add_parser("size", help="Show file sizes")
    size_parser.add_argument("paths", nargs="+", help="File paths")
    size_parser.set_defaults(func=cmd_size)
    
    # exists command
    exists_parser = subparsers.add_parser("exists", help="Check if paths exist")
    exists_parser.add_argument("paths", nargs="+", help="Paths to check")
    exists_parser.set_defaults(func=cmd_exists)
    
    # upload command
    upload_parser = subparsers.add_parser("upload", help="Upload local file or folder to artifact")
    upload_parser.add_argument("local_path", help="Local file or folder path")
    upload_parser.add_argument("remote_path", nargs="?", help="Remote path in artifact (default: same name)")
    upload_parser.add_argument("--recursive", action="store_true", default=True, help="Upload subdirectories recursively when uploading folders (default: true)")
    upload_parser.add_argument("--no-recursive", dest="recursive", action="store_false", help="Don't upload subdirectories")
    upload_parser.add_argument("--enable-multipart", action="store_true", help="Force multipart upload")
    upload_parser.add_argument("--multipart-threshold", type=int, default=100*1024*1024, help="File size threshold for multipart upload (bytes, default: 100MB)")
    upload_parser.add_argument("--chunk-size", type=int, default=10*1024*1024, help="Chunk size for multipart upload (bytes, default: 10MB)")
    upload_parser.set_defaults(func=cmd_upload)
    
    # download command
    download_parser = subparsers.add_parser("download", help="Download file from artifact")
    download_parser.add_argument("remote_path", help="Remote file path in artifact")
    download_parser.add_argument("local_path", nargs="?", help="Local file path (default: same name)")
    download_parser.set_defaults(func=cmd_download)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main() 