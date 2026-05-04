"""Shared runtime state for the SibPush add-on."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aqt import mw as _mw
from anki.notes import NoteId

mw: Any = _mw
last_checked_state: tuple[str, Sequence[NoteId]] | None = None
SUSPENDED_BY_ADDON_TAG = "SibPush-suspended"


def get_mw() -> Any:
    """Return the current Anki main window reference.

    Returns:
        Any: The current module-level `mw` handle.
    """

    return mw


def get_last_checked_state() -> tuple[str, Sequence[NoteId]] | None:
    """Return the cached batch-processing state.

    Returns:
        tuple[str, Sequence[anki.notes.NoteId]] | None: The last cached state, or None when
            the batch workflow has not run yet.
    """

    return last_checked_state


def sync_last_checked_state(state: tuple[str, Sequence[NoteId]] | None) -> None:
    """Update the cached batch-processing state.

    Args:
        state (tuple[str, Sequence[anki.notes.NoteId]] | None): The new cached state.

    Returns:
        None: The module-level cache is updated in place.
    """

    global last_checked_state
    last_checked_state = state
