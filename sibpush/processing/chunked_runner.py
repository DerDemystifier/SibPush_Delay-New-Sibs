"""Cooperative execution for potentially large main-thread workloads.

Anki's collection and scheduler APIs are synchronous, so large operations must be split into
small units and returned to Qt between those units. This module deliberately has no UI
knowledge: callers decide how to render progress, while the runner owns the event-loop handoff
and callback lifecycle.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from typing import Any, TypeVar, cast

from aqt.qt import QTimer

T = TypeVar("T")


def _get_chunk_size(batch_size: int, jitter: bool) -> int:
    """Return the next bounded chunk size, optionally varied by ten percent."""

    if not jitter:
        return batch_size

    variation = max(1, round(batch_size * 0.1))
    return random.randint(max(1, batch_size - variation), batch_size + variation)


def run_chunked(
    items: Sequence[T],
    process_chunk: Callable[[Sequence[T]], None],
    *,
    batch_size: int,
    pause_ms: int = 100,
    jitter: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
    on_complete: Callable[[], None] | None = None,
    on_success: Callable[[], None] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> None:
    """Process a sequence in bounded batches while yielding to Qt between batches.

    The first batch runs immediately so existing small, interactive operations retain their
    synchronous behavior. If more work remains, every subsequent batch is scheduled through
    ``QTimer.singleShot``. A single batch is therefore the maximum amount of work this helper
    can perform without returning to the event loop.

    ``on_progress`` receives ``(processed_count, total_count)`` after each processed batch. It
    is intentionally presentation-agnostic; callers may use it for a tooltip, log message, or
    no-op. ``should_continue`` is checked before every batch, including the first. Returning
    false stops cleanly, invokes ``on_complete``, and does not invoke ``on_success``.

    ``on_complete`` is invoked exactly once for all terminal outcomes, including an exception
    from ``process_chunk``, ``on_progress``, ``should_continue``, or ``on_success``. Exceptions
    are not swallowed; after cleanup they propagate to the caller/event loop.

    Args:
        items: Stable input sequence to process. It is copied before work begins.
        process_chunk: Side-effecting operation for one non-empty batch.
        batch_size: Maximum nominal number of items in a batch; must be positive.
        pause_ms: Delay before each subsequent batch; must be non-negative.
        jitter: Whether to vary each batch size by approximately ten percent.
        on_progress: Optional callback receiving processed and total item counts.
        on_complete: Optional callback that always runs once at termination.
        on_success: Optional callback that runs only after every item is processed.
        should_continue: Optional callback used to stop stale queued work safely.

    Returns:
        None. Work is performed for side effects.

    Raises:
        ValueError: If ``batch_size`` is not positive or ``pause_ms`` is negative.
        Exception: Any exception raised by processing or a callback, after completion cleanup.
    """

    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if pause_ms < 0:
        raise ValueError("pause_ms must be non-negative")

    pending_items = list(items)
    total_count = len(pending_items)
    completed = False

    def _finish(success: bool) -> None:
        nonlocal completed
        if completed:
            return

        completed = True
        try:
            if success and on_success is not None:
                on_success()
        finally:
            if on_complete is not None:
                on_complete()

    if not pending_items:
        _finish(True)
        return

    def _process_next(start_index: int) -> None:
        if start_index >= total_count:
            _finish(True)
            return

        try:
            if should_continue is not None and not should_continue():
                _finish(False)
                return

            chunk_size = _get_chunk_size(batch_size, jitter)
            chunk = pending_items[start_index : start_index + chunk_size]
            if not chunk:
                _finish(True)
                return

            process_chunk(cast(Sequence[T], chunk))
            next_index = start_index + len(chunk)
            if on_progress is not None:
                on_progress(min(next_index, total_count), total_count)

            if next_index >= total_count:
                _finish(True)
                return

            cast(Any, QTimer).singleShot(
                pause_ms,
                lambda next_start_index=next_index: _process_next(next_start_index),
            )
        except Exception:
            _finish(False)
            raise

    _process_next(0)
