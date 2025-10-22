"""Sync utilities for running async code.

Centralizes the logic for executing awaitables from synchronous code, including an
optional override using ``pyodide.ffi.run_sync`` when available.
"""

from __future__ import annotations

import asyncio
import importlib
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable

T = TypeVar("T")

try:
    _pyodide_run_sync = importlib.import_module("pyodide.ffi").run_sync
except (ImportError, AttributeError):  # pragma: no cover - only on CPython environments
    _pyodide_run_sync = None


def _default_run_sync(awaitable: Awaitable[T]) -> T:
    """Return the awaitable's result by driving it to completion with asyncio.

    Creates a new loop when necessary or when the current loop is running.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(awaitable)
            finally:
                new_loop.close()
        return loop.run_until_complete(awaitable)
    except RuntimeError:
        # No event loop in this thread
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(awaitable)
        finally:
            new_loop.close()


def run_sync(awaitable: Awaitable[T]) -> T:
    """Run an awaitable synchronously with proper typing preserved."""
    if _pyodide_run_sync is not None:  # type: ignore[truthy-bool]
        return _pyodide_run_sync(awaitable)  # type: ignore[no-any-return]
    return _default_run_sync(awaitable)


__all__ = ["run_sync"]
