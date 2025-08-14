"""Sync utilities for running async code."""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine in a sync context.

    This function provides a way to execute an awaitable coroutine from synchronous code
    by managing the asyncio event loop. It ensures that a new event loop is created
    if one is not already running in the current thread.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)
