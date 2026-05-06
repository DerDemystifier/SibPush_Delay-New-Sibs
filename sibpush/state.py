"""Shared runtime state for the SibPush add-on."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from aqt import mw as _mw
from anki.notes import NoteId

mw: Any = _mw
last_full_scan_date: str | None = None
last_unmanaged_note_ids: Sequence[NoteId] | None = None
SUSPENDED_BY_ADDON_TAG = "SibPush-suspended"


def get_mw() -> Any:
    """Return the current Anki main window reference.

    Returns:
        Any: The current module-level `mw` handle.
    """

    return mw


def get_last_full_scan_date() -> str | None:
    """Return the date of the most recent full browser-driven scan.

    Returns:
        str | None: The ISO date of the last completed full scan, or None when it has not run yet.
    """

    return last_full_scan_date


def sync_last_full_scan_date(value: str | None) -> None:
    """Update the cached date for the most recent full browser-driven scan.

    Args:
        value (str | None): The new ISO date for the completed full scan.

    Returns:
        None: The module-level cache is updated in place.
    """

    global last_full_scan_date
    last_full_scan_date = value


def get_last_unmanaged_note_ids() -> Sequence[NoteId] | None:
    """Return the note ids from the last unmanaged-note batch processing pass.

    Returns:
        Sequence[anki.notes.NoteId] | None: The last cached unmanaged note ids, or None when
            the unmanaged workflow has not run yet.
    """

    return last_unmanaged_note_ids


def sync_last_unmanaged_note_ids(note_ids: Sequence[NoteId] | None) -> None:
    """Update the cached unmanaged-note batch-processing note ids.

    Args:
        note_ids (Sequence[anki.notes.NoteId] | None): The new unmanaged note ids.

    Returns:
        None: The module-level cache is updated in place.
    """

    global last_unmanaged_note_ids
    last_unmanaged_note_ids = note_ids
