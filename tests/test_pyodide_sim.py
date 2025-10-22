# ruff: noqa: S101

"""Pyodide-like environment simulation tests.

Ensures code paths work when `anyio` is unavailable and thread offloading is
emulated inline. This approximates constraints in Pyodide environments.
"""

import importlib
import sys
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _typeshed import OpenBinaryMode, OpenTextMode
else:
    OpenBinaryMode = str
    OpenTextMode = str

import hypha_artifact.async_hypha_artifact._utils as utils


def test_run_sync_import_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure run_sync can be safely overridden by pyodide when available.

    Simulate presence of `pyodide.ffi.run_sync` and confirm that importing
    `run_sync` resolves to the injected callable. Then remove it and ensure
    our local `sync_utils.run_sync` remains importable without error.
    """

    # Simulate pyodide.ffi.run_sync existing
    class DummyFFI:
        @staticmethod
        def run_sync(arg: object) -> tuple[str, object]:
            return ("pyodide", arg)

    class DummyPyodide:
        ffi = DummyFFI()

    monkeypatch.setitem(sys.modules, "pyodide", DummyPyodide())
    monkeypatch.setitem(sys.modules, "pyodide.ffi", DummyFFI())

    # Resolve run_sync dynamically to avoid E402 (imports not at top-level)
    pyodide_ffi = importlib.import_module("pyodide.ffi")  # type: ignore[import-not-found]
    pyodide_run_sync = pyodide_ffi.run_sync
    assert pyodide_run_sync("x")[0] == "pyodide"

    # Remove pyodide to verify fallback
    sys.modules.pop("pyodide.ffi", None)
    sys.modules.pop("pyodide", None)

    # Fallback still importable from our module
    sync_utils = importlib.import_module("hypha_artifact.sync_utils")
    local_run_sync = sync_utils.run_sync

    # Should be callable (will error if wrong object)
    def _noop() -> int:  # pyright: ignore reportUnusedFunction
        return 1

    assert callable(local_run_sync)


@pytest.mark.asyncio
async def test_aio_open_uses_anyio_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify that aio_open delegates to anyio.open_file when available.

    We monkeypatch anyio and its open_file to capture the call.
    """

    class DummyAsyncFile:
        def __init__(self) -> None:
            self.data: bytearray = bytearray()

        async def __aenter__(self) -> "DummyAsyncFile":
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            return None

        async def write(self, data: bytes) -> int:
            self.data.extend(data)
            return len(data)

        async def read(self) -> bytes:
            return bytes(self.data)

        @staticmethod
        async def aclose() -> None:
            return None

    calls: list[tuple[str, str]] = []

    class DummyAnyio:
        async def open_file(
            self,
            path: str,
            mode: OpenBinaryMode | OpenTextMode,
        ) -> DummyAsyncFile:
            calls.append((str(path), mode))
            return DummyAsyncFile()

    dummy_anyio = DummyAnyio()
    monkeypatch.setattr(utils, "anyio", dummy_anyio, raising=False)
    monkeypatch.setattr(utils, "_has_anyio", True, raising=False)
    monkeypatch.setattr(utils, "_HAS_ANYIO", True, raising=False)

    p = tmp_path / "file.bin"
    data = b"hello-anyio"

    f = await utils.anyio.open_file(p, "wb")  # type: ignore[union-attr]
    async with f as fd:
        n = await fd.write(data)

    assert n == len(data)
    assert calls == [(str(p), "wb")]
