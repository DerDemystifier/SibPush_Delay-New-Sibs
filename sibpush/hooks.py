"""Anki hook callbacks for the SibPush add-on."""

from __future__ import annotations

import logging
from typing import Any

from anki.cards import Card
from anki.collection import Collection
from aqt import gui_hooks

from .config.migration import migrate_legacy_config
from .config.parser import on_config_save
from .logging_support import initialize_log_file
from .processing.notes import process_all_notes, process_note


def collection_did_load(col: Collection) -> None:
    """Run startup tasks once Anki loads the collection.

    Args:
        col (anki.collection.Collection): The collection that was just loaded.

    Returns:
        None: The startup tasks are performed for their side effects.
    """

    migrate_legacy_config()
    initialize_log_file()


def browser_render(browser: Any) -> None:
    """Process notes when the Deck Browser refreshes.

    Args:
        browser (Any): The browser instance emitted by the hook.

    Returns:
        None: The browser's collection is processed in place.
    """

    if not browser or not browser.mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    process_all_notes(browser.mw.col)


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

    gui_hooks.collection_did_load.append(collection_did_load)
    gui_hooks.deck_browser_did_render.append(browser_render)
    gui_hooks.reviewer_did_answer_card.append(reviewer_did_answer_card)
    gui_hooks.addon_config_editor_will_update_json.append(on_config_save)
    gui_hooks.addons_dialog_will_delete_addons.append(on_addon_delete)
