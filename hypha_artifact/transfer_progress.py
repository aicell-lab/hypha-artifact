"""Progress handler for transfers."""

import logging
import sys
from pathlib import Path
from typing import Any

try:  # optional dependency for nicer progress bars
    from tqdm import tqdm  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback when tqdm isn't available
    tqdm = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TransferProgress:
    """Lightweight progress handler for CLI operations."""

    def __init__(self, operation: str) -> None:
        """Initialize the progress handler.

        Args:
            operation (str): The operation being
                performed (e.g., "upload" or "download").

        """
        self.operation = operation
        self.total = None
        self.completed = 0
        self.pbar = None  # files-level bar
        self._part_bars: dict[str, Any] = {}
        self._parts_done: dict[str, int] = {}
        self._parts_total: dict[str, int] = {}

    def _fallback_write(self, msg: str) -> None:
        try:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except OSError:  # pragma: no cover - extremely unlikely
            logger.debug("stderr write failed for progress message")

    def _init_progress(self, total: int) -> None:
        self.total = total
        if tqdm is not None:
            desc = "Uploading" if self.operation == "upload" else "Downloading"
            self.pbar = tqdm(
                total=total,
                desc=desc,
                unit="file",
                dynamic_ncols=True,
                leave=False,
                position=0,
            )
        else:
            self._fallback_write(
                f"{self.operation.capitalize()}ing {total} file(s)...",
            )

    def _on_success(self) -> None:
        self.completed += 1
        if self.pbar is not None:
            self.pbar.update(1)
            if isinstance(self.total, int) and self.completed >= self.total:
                self.pbar.close()
        elif isinstance(self.total, int):
            if self.completed in (1, self.total) or self.completed % 10 == 0:
                self._fallback_write(
                    f"{self.operation.capitalize()} progress: "
                    f"{self.completed}/{self.total}",
                )

    def _on_error(self, file_path: str, message: str) -> None:
        if self.pbar is not None:
            self.pbar.write(f"Error {self.operation} {file_path}: {message}")
            self.pbar.update(1)
        else:
            self._fallback_write(
                f"Error {self.operation} {file_path}: {message}",
            )

    def __call__(self, event: dict[str, Any]) -> None:
        """Handle progress events.

        Args:
            event (dict[str, Any]): The event data.

        """
        etype = event.get("type")
        if etype == "info":
            total = event.get("total_files")
            if self.total is None and isinstance(total, int):
                self._init_progress(total)
            return
        if etype == "success":
            self._on_success()
            return
        if etype == "error":
            self._on_error(
                str(event.get("file", "?")),
                str(event.get("message", "")),
            )
            return
        if etype in {"part_info", "part_success", "part_error"}:
            self._handle_part_event(event)
            return

    def _handle_part_event(self, event: dict[str, Any]) -> None:
        file_path = str(event.get("file", "?"))
        total_parts = event.get("total_parts")
        if isinstance(total_parts, int) and file_path not in self._part_bars:
            self._parts_total[file_path] = total_parts
            self._parts_done[file_path] = 0
            if tqdm is not None:
                desc = f"Uploading {Path(file_path).name}"
                self._part_bars[file_path] = tqdm(
                    total=total_parts,
                    desc=desc,
                    unit="part",
                    dynamic_ncols=True,
                    leave=False,
                    position=1,
                )
            else:
                self._fallback_write(
                    f"{self.operation.capitalize()}ing parts: 0/{total_parts}",
                )

        etype = event.get("type")
        if etype in {"part_success", "part_error"}:
            self._parts_done[file_path] = self._parts_done.get(file_path, 0) + 1
            bar = self._part_bars.get(file_path)
            if bar is not None:
                bar.update(1)
                if self._parts_done[file_path] >= self._parts_total.get(file_path, 0):
                    bar.close()
                    self._part_bars.pop(file_path, None)
                    self._parts_done.pop(file_path, None)
                    self._parts_total.pop(file_path, None)
            else:
                done = self._parts_done[file_path]
                tot = self._parts_total.get(file_path, 0)
                self._fallback_write(
                    f"{self.operation.capitalize()}ing parts: {done}/{tot}",
                )
