"""Utilities for composing add-on operations with existing Anki undo entries."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager

from anki.collection import Collection

from ..logging_support import logThis


def _merge_entries_since(
    col: Collection, target_step: int, *, skip_if_empty_target: bool
) -> None:
    try:
        last_step = col.undo_status().last_step
        step_changed = last_step != target_step
        target_exists = bool(target_step)
        if not step_changed:
            return
        if skip_if_empty_target and not target_exists:
            return
        col.merge_undo_entries(target_step)
    except Exception as error:
        error_message = str(error)
        logThis(
            lambda: (
                f"SibPush failed to merge undo entries into step {target_step}: "
                f"{error_message}"
            )
        )


@contextmanager
def merge_into_top_undo_entry(col: Collection) -> Generator[None, None, None]:
    """Merge undoable operations in the context into the existing top undo entry.

    The target entry retains its Anki-provided label. Undo entries created by synchronous
    work performed within the context are merged as well. If no prior entry exists, no merge
    is attempted and Anki's new undo entries remain separate.
    """

    target_step: int | None = None
    try:
        target_step = col.undo_status().last_step
    except Exception as error:
        error_message = str(error)
        logThis(
            lambda: (
                "SibPush failed to read the current undo step before processing: "
                f"{error_message}"
            )
        )

    if target_step is None:
        yield
        return

    try:
        yield
    finally:
        _merge_entries_since(col, target_step, skip_if_empty_target=True)


@contextmanager
def custom_undo_entry(
    col: Collection, name: str
) -> Generator[Callable[[], None], None, None]:
    """Lazily create a named entry and merge changes made within the context into it.

    Call the yielded function immediately before the first collection mutation. If no mutation
    is needed, no custom undo entry is added. If the first mutation raises before recording its
    own undo change, Anki may retain the empty named entry.
    """

    target_step: int | None = None

    def _start_entry() -> None:
        nonlocal target_step
        if target_step is None:
            target_step = col.add_custom_undo_entry(name)

    try:
        yield _start_entry
    finally:
        if target_step is not None:
            _merge_entries_since(col, target_step, skip_if_empty_target=False)
