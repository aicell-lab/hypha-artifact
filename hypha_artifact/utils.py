"""Shared utility functions for hypha_artifact.

These helpers are intentionally free of async/sync coupling and can be reused
across both the async and sync APIs.
"""

from __future__ import annotations

import os
from pathlib import Path


def local_file_or_dir(src_path: str, dst_path: str) -> str:
    """Resolve destination semantics without using the local filesystem.

    - If `dst_path` ends with a path separator (`/` on POSIX), treat it as a
      directory hint and append the basename of `src_path`.
    - Otherwise, treat `dst_path` as the full target path.

    This avoids surprising behavior when a local directory happens to share
    the same name as the intended file (e.g., a directory named 'file.txt').
    """
    is_dir_hint = str(dst_path).endswith(("/", os.sep))
    return str(Path(dst_path) / Path(src_path).name) if is_dir_hint else str(dst_path)


def env_override(
    env_var_name: str,
    *,
    override: bool | str | None = None,
) -> bool | str | None:
    """Return the effective value for an env var with an optional override.

    - If ``override`` is not None, return it.
    - Else, if the environment variable is set, coerce "true" (case-insensitive)
      to True; otherwise return the raw string value.
    - Else, return None.
    """
    env_var_val = os.getenv(env_var_name)

    if override is not None:
        return override

    if env_var_val is not None:
        if env_var_val.lower() == "true":
            return True
        return env_var_val

    return None


def to_bytes(content: str | bytes | bytearray | memoryview) -> bytes:
    """Coerce common text/byte-like values into bytes."""
    if isinstance(content, bytes):
        return content
    if isinstance(content, str):
        return content.encode("utf-8")
    return bytes(content)


def decode_to_text(content: str | bytes | bytearray | memoryview) -> str:
    """Decode common text/byte-like values into str using UTF-8."""
    if isinstance(content, str):
        return content
    if isinstance(content, bytes):
        return content.decode("utf-8")
    return bytes(content).decode("utf-8")


def local_walk(
    src_path: str,
    maxdepth: int | None = None,
) -> list[str]:
    """Find all files in a local directory up to an optional depth."""
    files: list[str] = []
    for root, _, dir_files in os.walk(src_path):
        if maxdepth is not None:
            rel_path = Path(root).relative_to(src_path)
            if len(rel_path.parts) >= maxdepth:
                continue
        files.extend(str(Path(root) / file_name) for file_name in dir_files)

    return files


def rel_path_pairs(
    files: list[str],
    src_path: str,
    dst_path: str,
) -> list[tuple[str, str]]:
    """Map absolute file paths to destination paths preserving relative structure."""
    file_pairs: list[tuple[str, str]] = []
    dst_base = Path(dst_path)
    for f in files:
        rel = Path(f).relative_to(src_path)
        file_pairs.append((f, str(dst_base / rel)))
    return file_pairs


def ensure_equal_len(
    rpath: str | list[str],
    lpath: str | list[str],
) -> tuple[list[str], list[str]]:
    """Assert that two paths (or lists of paths) are of equal length and type.

    Returns both arguments as lists for easier zipping.
    """
    if isinstance(rpath, str) and isinstance(lpath, str):
        rpath = [rpath]
        lpath = [lpath]
    elif isinstance(rpath, list) and isinstance(lpath, list):
        if len(rpath) != len(lpath):
            msg = "Both rpath and lpath must be the same length."
            raise ValueError(msg)
    else:
        msg = "Both rpath and lpath must be strings or lists of strings."
        raise TypeError(msg)

    return rpath, lpath
