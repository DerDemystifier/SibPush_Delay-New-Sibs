"""Anki hook callbacks for the SibPush add-on.

This module registers the Anki hooks that drive SibPush's sibling management.
The add-on uses several hooks to monitor and respond to user actions:

1. collection_did_load: Initialize on startup and load persistent state
2. browser_render: Run the timestamp-based browser scan
3. reviewer_did_answer_card: Process one note after a review action
4. sync_did_finish: Refresh unmanaged notes and persist the sync watermark
5. addon_config_editor_will_update_json: Handle config changes
6. addons_dialog_will_delete_addons: Clean shutdown

The processing model now uses persisted timestamps instead of a day gate:
- Browser renders scan modified notes since the older of the sync and processed watermarks.
- Sync completion updates the sync watermark so browser scans can catch up with remote edits.
- The lighter unmanaged-note pass still runs after sync to revisit fresh notes that have not yet
    been tagged by the add-on.
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from anki.cards import Card
from anki.collection import Collection
from aqt import gui_hooks
from aqt.qt import QTimer

from .config.migration import migrate_legacy_config
from .config.parser import on_config_save
from .logging_support import initialize_log_file
from .processing.notes import process_modified_notes, process_new_unmanaged_notes, process_note
from .state import (
    get_browser_scan_since_ts,
    get_mw,
    load_persistent_state,
    save_persistent_state,
    sync_last_sync_mod_ts,
)
from .ui.deck_actions import add_deck_actions_to_options_menu

_pending_browser_scan = False


def collection_did_load(col: Collection) -> None:
    """Run startup tasks once Anki loads the collection.

    Args:
        col (anki.collection.Collection): The collection that was just loaded.

    Returns:
        None: The startup tasks are performed for their side effects.
    """

    migrate_legacy_config()
    initialize_log_file()
    load_persistent_state(col)


def browser_render(browser: Any) -> None:
    """Process notes when the Deck Browser refreshes.

    This entry point uses the persisted timestamp watermark instead of a day-based gate.
    Each browser render schedules a timestamp-bounded scan, and the scan itself persists the new
    processed watermark when it completes.

    Args:
        browser (Any): The browser instance emitted by the hook.

    Returns:
        None: The browser's collection is processed in place.
    """

    if not browser or not browser.mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    global _pending_browser_scan

    if _pending_browser_scan:
        # A browser scan is already scheduled - don't queue another one.
        return

    _pending_browser_scan = True

    def _clear_pending_browser_scan() -> None:
        global _pending_browser_scan
        _pending_browser_scan = False

    process_modified_notes(
        browser.mw.col, get_browser_scan_since_ts(), on_complete=_clear_pending_browser_scan
    )


def reviewer_did_answer_card(reviewer: Any, card: Card, ease: int) -> None:
    """Process a note after the reviewer answers one of its cards.

    Args:
        reviewer (Any): The reviewer instance emitted by the hook.
        card (anki.cards.Card): The card that was answered.
        ease (int): The selected answer ease.

    Returns:
        None: The note is updated in place.
    """

    if not reviewer or not reviewer.mw or not reviewer.mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    process_note(reviewer.mw.col, card.nid, coming_from_reviewer_hook=True)


def sync_did_finish(*_args: Any) -> None:
    """Process newly synced unmanaged notes and persist the sync watermark."""

    current_mw = get_mw()
    if current_mw is None or not getattr(current_mw, "col", None):
        raise Exception("SibPush : Anki is not initialized properly")

    process_new_unmanaged_notes(current_mw.col)
    sync_last_sync_mod_ts(int(time.time()))
    save_persistent_state(current_mw.col)


def on_addon_delete(dialog: Any, ids: list[str]) -> None:
    """Shut down logging when the add-on is being deleted.

    Args:
        dialog (Any): The add-ons dialog instance.
        ids (list[str]): The ids selected for deletion.

    Returns:
        None: The logging system is shut down for a clean exit.
    """

    logging.shutdown()


def register_hooks() -> None:
    """Register the add-on's Anki hooks.

    Returns:
        None: Hook registration happens for its side effects.
    """

    hooks = cast(Any, gui_hooks)

    # Startup hooks.
    hooks.collection_did_load.append(collection_did_load)

    # Main processing hooks.
    hooks.deck_browser_did_render.append(browser_render)
    hooks.reviewer_did_answer_card.append(reviewer_did_answer_card)
    hooks.sync_did_finish.append(sync_did_finish)

    # UI/config hooks.
    hooks.deck_browser_will_show_options_menu.append(add_deck_actions_to_options_menu)
    hooks.addon_config_editor_will_update_json.append(on_config_save)
    hooks.addons_dialog_will_delete_addons.append(on_addon_delete)
