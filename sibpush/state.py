"""Shared runtime state for the SibPush add-on."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aqt import mw as _mw
from anki.notes import NoteId

mw: Any = _mw

# These caches intentionally track two different triggers:
# - `last_full_scan_date` gates the expensive browser-driven scan.
# - `last_unmanaged_note_ids` gates the lighter follow-up pass that only revisits
#   new notes that are still unmanaged by the add-on.
last_full_scan_date: str | None = None
last_unmanaged_note_ids: Sequence[NoteId] | None = None

# Persistent, collection-scoped state used by the future timestamp-based scan flow.
last_processed_mod_ts: int | None = None
last_sync_mod_ts: int | None = None

SUSPENDED_BY_ADDON_TAG = "SibPush-suspended"
STATE_FILENAME = "sibpush_state.json"
_persistent_state_loaded = False


def get_mw() -> Any:
    """Return the current Anki main window reference.

    Returns:
        Any: The current module-level `mw` handle.
    """

    return mw


def _resolve_collection_path(col: Any | None = None) -> Path | None:
    """Return the filesystem path for the active collection, if available."""

    current_col = col
    if current_col is None:
        current_mw = get_mw()
        current_col = getattr(current_mw, "col", None) if current_mw is not None else None

    if current_col is None:
        return None

    raw_path = getattr(current_col, "path", None)
    if not raw_path:
        return None

    return Path(str(raw_path))


def get_state_file_path(col: Any | None = None) -> Path | None:
    """Return the per-collection state file path.

    Args:
        col (Any | None): The collection to resolve the path from. When omitted,
            the current ``mw.col`` value is used.

    Returns:
        Path | None: The sibling ``sibpush_state.json`` path, or None when no collection path exists.
    """

    collection_path = _resolve_collection_path(col)
    if collection_path is None:
        return None

    return collection_path.with_name(STATE_FILENAME)


def _normalize_timestamp(value: Any) -> int | None:
    """Convert a state timestamp to a non-negative integer, if possible."""

    if value is None:
        return None

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None

    return timestamp if timestamp >= 0 else None


def _read_state_payload(state_file: Path) -> dict[str, Any]:
    """Read a JSON payload from disk, falling back to an empty object on errors."""

    try:
        with state_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}

    if not isinstance(payload, dict):
        return {}

    return payload


def _write_state_payload(state_file: Path, payload: dict[str, Any]) -> None:
    """Write a JSON payload atomically to disk."""

    state_file.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state_file.parent,
            prefix=f"{state_file.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)

        os.replace(temp_path, state_file)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def get_last_processed_mod_ts() -> int:
    """Return the last processed modification timestamp.

    Returns:
        int: ``0`` when no timestamp has been persisted yet.
    """

    return last_processed_mod_ts if last_processed_mod_ts is not None else 0


def sync_last_processed_mod_ts(value: int | None) -> None:
    """Update the cached timestamp for the last processed note batch."""

    global last_processed_mod_ts
    last_processed_mod_ts = _normalize_timestamp(value)


def get_last_sync_mod_ts() -> int | None:
    """Return the last sync modification timestamp, if one exists."""

    return last_sync_mod_ts


def get_browser_scan_since_ts() -> int:
    """Return the timestamp threshold the browser scan should use.

    When both a last-sync watermark and a last-processed watermark exist, the browser scan should
    use the older one so we do not miss cards that changed on another device before the local
    browser scan ran.
    """

    processed_ts = get_last_processed_mod_ts()
    sync_ts = get_last_sync_mod_ts()
    if sync_ts is None:
        return processed_ts

    return min(processed_ts, sync_ts)


def sync_last_sync_mod_ts(value: int | None) -> None:
    """Update the cached timestamp for the last successful sync."""

    global last_sync_mod_ts
    last_sync_mod_ts = _normalize_timestamp(value)


def get_persistent_state() -> dict[str, int | None]:
    """Return a snapshot of the persistent state currently held in memory."""

    return {
        "last_processed_mod_ts": get_last_processed_mod_ts(),
        "last_sync_mod_ts": get_last_sync_mod_ts(),
    }


def load_persistent_state(col: Any | None = None) -> dict[str, int | None]:
    """Load persistent state from ``sibpush_state.json`` for the current collection."""

    state_file = get_state_file_path(col)
    if state_file is None or not state_file.exists():
        _apply_state_payload({})
        return get_persistent_state()

    payload = _read_state_payload(state_file)
    _apply_state_payload(payload)
    return get_persistent_state()


def save_persistent_state(col: Any | None = None) -> dict[str, int | None]:
    """Persist the current timestamp state to ``sibpush_state.json``."""

    state_file = get_state_file_path(col)
    if state_file is None:
        return get_persistent_state()

    payload: dict[str, Any] = {}
    if last_processed_mod_ts is not None:
        payload["last_processed_mod_ts"] = last_processed_mod_ts
    if last_sync_mod_ts is not None:
        payload["last_sync_mod_ts"] = last_sync_mod_ts

    _write_state_payload(state_file, payload)
    return get_persistent_state()


def reset_persistent_state(col: Any | None = None) -> dict[str, int | None]:
    """Clear the persisted timestamps and reset the in-memory scan state."""

    global last_full_scan_date, last_unmanaged_note_ids, last_processed_mod_ts, last_sync_mod_ts
    global _persistent_state_loaded

    last_full_scan_date = None
    last_unmanaged_note_ids = None
    last_processed_mod_ts = None
    last_sync_mod_ts = None
    _persistent_state_loaded = True

    state_file = get_state_file_path(col)
    if state_file is not None:
        _write_state_payload(state_file, {})

    return get_persistent_state()


def _apply_state_payload(payload: dict[str, Any]) -> None:
    """Apply a JSON payload to the in-memory timestamp state."""

    global last_processed_mod_ts, last_sync_mod_ts, _persistent_state_loaded

    last_processed_mod_ts = _normalize_timestamp(payload.get("last_processed_mod_ts"))
    last_sync_mod_ts = _normalize_timestamp(payload.get("last_sync_mod_ts"))
    _persistent_state_loaded = True


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
