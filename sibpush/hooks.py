"""Anki hook callbacks for the SibPush add-on.

This module registers the Anki hooks that drive SibPush's sibling management.
The add-on uses several hooks to monitor and respond to user actions:

1. collection_did_load: Initialize on startup and load persistent state
2. browser_render: Run the timestamp-based browser scan
3. reviewer_did_answer_card: Process one note after a review action
4. sync_did_finish: Queue unmanaged-note refresh and persist the sync watermark
5. collection_will_temporarily_close: Queue a full reprocessing pass before one-way syncs
6. addon_config_editor_will_display_json: Load the profile-local config into the editor
7. addon_config_editor_will_update_json: Handle config changes
8. addons_dialog_will_delete_addons: Clean shutdown

The processing model now uses persisted timestamps instead of a day gate:
- Browser renders scan modified notes since the older of the sync and processed watermarks.
- Browser renders also drain deferred config/sync work before scanning.
- Sync completion updates the sync watermark so browser scans can catch up with remote edits.
- The lighter unmanaged-note pass now runs from browser render after sync queues it, so fresh
    notes still get revisited without making sync itself a batch-processing entry point.
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
from .config.parser import load_config_state, on_config_display, on_config_save
from .logging_support import initialize_log_file
from .processing.notes import (
    process_modified_notes,
    process_new_unmanaged_notes,
    process_note,
    show_processing_finished_tooltip,
)
from .processing.suspension import unsuspend_all_addon_cards
from .state import (
    consume_pending_browser_work,
    clear_stale_sync_mod_ts,
    get_browser_scan_since_ts,
    get_mw,
    load_persistent_state,
    queue_pending_browser_work,
    reset_persistent_state,
    save_persistent_state,
    sync_last_sync_mod_ts,
)
from .processing.suspension import unsuspend_all_addon_cards_in_deck
from .ui.deck_actions import add_deck_actions_to_options_menu

_BROWSER_SCAN_DELAY_MS = 2000
_pending_browser_scan = False


def _addon_module_name() -> str:
    """Return the top-level module name for this add-on package."""

    package_name = __package__ or __name__
    return package_name.split(".", 1)[0]


# Keep the tooltip helper imported for tests and for parity with the processing module's
# completion path, even though this module does not invoke it directly.
_ = show_processing_finished_tooltip


def _apply_pending_browser_work_before_scan(
    col: Collection, pending_browser_work: dict[str, Any]
) -> None:
    """Apply queued browser work that must happen before the modified-note scan.

    Args:
        col (anki.collection.Collection): The active collection for the browser session.
        pending_browser_work (dict[str, Any]): The queued browser-work snapshot to consume.

    Returns:
        None: The queued pre-scan side effects are applied to the collection.
    """

    if pending_browser_work["pending_processing_state_reset"]:
        reset_persistent_state(col)

    for deck_id in pending_browser_work["pending_unsuspend_deck_ids"]:
        unsuspend_all_addon_cards_in_deck(col, str(deck_id))


def _apply_pending_browser_work_after_scan(
    col: Collection, pending_browser_work: dict[str, Any]
) -> None:
    """Apply queued browser work that should happen after the modified-note scan.

    Args:
        col (anki.collection.Collection): The active collection for the browser session.
        pending_browser_work (dict[str, Any]): The queued browser-work snapshot to consume.

    Returns:
        None: The queued post-scan side effects are applied to the collection.
    """

    if pending_browser_work["pending_unmanaged_refresh"]:
        process_new_unmanaged_notes(col)


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
    load_config_state(col)


def addon_config_editor_will_display_json(text: str) -> str:
    """Show the profile-local config when the Add-ons Config panel opens.

    Args:
        text (str): The JSON text Anki is about to display.

    Returns:
        str: The JSON text to show in the editor.
    """

    return on_config_display(text)


def browser_render(browser: Any) -> None:
    """Process notes when the Deck Browser refreshes.

    This entry point acts as the central batch dispatcher. It first applies any queued
    browser-work side effects, then schedules the timestamp-bounded scan after a short delay.
    The scan itself persists the new processed watermark when it completes, and any queued
    unmanaged-note refresh is run after the modified-note pass.

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

    col = browser.mw.col

    def _clear_pending_browser_scan() -> None:
        global _pending_browser_scan
        _pending_browser_scan = False

    def _run_browser_render() -> None:
        pending_browser_work = consume_pending_browser_work()

        # Consume the queue once so we do not replay config or sync work on the next render.
        # Apply pre-scan work first so the modified-note query sees the latest ignore/reset state.
        _apply_pending_browser_work_before_scan(col, pending_browser_work)
        browser_scan_since_ts = get_browser_scan_since_ts()

        def _after_modified_scan_success() -> None:
            if clear_stale_sync_mod_ts():
                save_persistent_state(col)

            if browser_scan_since_ts > 0:
                _apply_pending_browser_work_after_scan(col, pending_browser_work)

        try:
            process_modified_notes(
                col,
                browser_scan_since_ts,
                on_complete=_clear_pending_browser_scan,
                on_success=_after_modified_scan_success,
            )
        except Exception:
            _clear_pending_browser_scan()
            raise

    cast(Any, QTimer).singleShot(_BROWSER_SCAN_DELAY_MS, _run_browser_render)


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
    """Queue unmanaged-note refresh and persist the sync watermark.

    Returns:
        None: Sync bookkeeping is updated immediately, but note processing is deferred to the
        next browser render.
    """

    current_mw = get_mw()
    if current_mw is None or not getattr(current_mw, "col", None):
        raise Exception("SibPush : Anki is not initialized properly")

    # Sync only records the new watermark and sets a follow-up flag; browser render performs
    # the actual note processing later.
    sync_last_sync_mod_ts(int(time.time()))
    queue_pending_browser_work(refresh_unmanaged_notes=True)
    save_persistent_state(current_mw.col)


def collection_will_temporarily_close(col: Collection) -> None:
    """Queue a full browser reprocessing pass before Anki temporarily closes the collection.

    This hook runs before one-way syncs and colpkg import/export operations. Those flows can
    rewrite note/card modification timestamps or revert previously processed cards, so we treat
    them as a boundary that invalidates the current scan watermark.

    Args:
        col (anki.collection.Collection): The collection that is about to be closed temporarily.

    Returns:
        None: The next browser render will perform a full modified-note rescan.
    """

    # Queue a full reset rather than trying to infer which rows changed. One-way syncs and
    # import/export operations can make `notes.mod` and `cards.mod` move backwards, so the
    # timestamp window is no longer trustworthy after this boundary.
    queue_pending_browser_work(reset_processing_state=True)
    save_persistent_state(col)


def on_addon_delete(dialog: Any, ids: list[str]) -> None:
    """Restore add-on-managed cards before the add-on is deleted.

    Args:
        dialog (Any): The add-ons dialog instance.
        ids (list[str]): The ids selected for deletion.

    Returns:
        None: The add-on's cards are restored immediately before logging shuts down.
    """

    if _addon_module_name() in ids:
        current_mw = get_mw()
        if current_mw is not None and getattr(current_mw, "col", None):
            unsuspend_all_addon_cards(current_mw.col)

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
    hooks.collection_will_temporarily_close.append(collection_will_temporarily_close)

    # UI/config hooks.
    hooks.deck_browser_will_show_options_menu.append(add_deck_actions_to_options_menu)
    hooks.addon_config_editor_will_display_json.append(addon_config_editor_will_display_json)
    hooks.addon_config_editor_will_update_json.append(on_config_save)
    hooks.addons_dialog_will_delete_addons.append(on_addon_delete)
