"""Deck-browser actions for managing SibPush per-deck rules."""

from __future__ import annotations

from typing import Any

from aqt.qt import QInputDialog, QMenu

from ..config.parser import get_custom_deck_rule_snapshot, update_custom_deck_rule
from ..state import get_mw


def _get_collection() -> Any | None:
    """Return the active collection, if Anki is ready."""

    current_mw = get_mw()
    if current_mw is None:
        return None

    return getattr(current_mw, "col", None)


def _get_deck_name(col: Any, deck_id: int) -> str:
    """Return the readable deck name for a deck id."""

    deck = col.decks.get(deck_id)
    if isinstance(deck, dict):
        return str(deck.get("name", deck_id)).strip() or str(deck_id)

    return str(deck_id)


def _toggle_ignore_state(deck_id: int) -> None:
    """Flip the ignore state for one deck."""

    col = _get_collection()
    if col is None:
        return

    deck_name = _get_deck_name(col, deck_id)
    snapshot = get_custom_deck_rule_snapshot(str(deck_id))
    update_custom_deck_rule(
        str(deck_id),
        deck_name,
        ignored=not snapshot["ignored"],
        interval=snapshot["interval"],
    )


def _set_custom_interval(deck_id: int) -> None:
    """Prompt for and save a custom interval for one deck."""

    col = _get_collection()
    if col is None:
        return

    deck_name = _get_deck_name(col, deck_id)
    snapshot = get_custom_deck_rule_snapshot(str(deck_id))
    value, accepted = QInputDialog.getInt(
        get_mw(),
        "Set SibPush deck interval",
        f"Enter the maturity interval for '{deck_name}'",
        snapshot["interval"],
        0,
        100000,
        1,
    )
    if not accepted:
        return

    update_custom_deck_rule(
        str(deck_id),
        deck_name,
        ignored=snapshot["ignored"],
        interval=value,
    )


def add_deck_actions_to_options_menu(menu: QMenu, deck_id: int) -> None:
    """Add the SibPush submenu to the deck browser options menu."""

    if deck_id is None:
        return

    col = _get_collection()
    if col is None:
        return

    snapshot = get_custom_deck_rule_snapshot(str(deck_id))
    submenu = menu.addMenu("SibPush")

    ignore_label = "Unignore current deck" if snapshot["ignored"] else "Ignore current deck"
    ignore_action = submenu.addAction(ignore_label)
    ignore_action.triggered.connect(
        lambda _checked=False, did=deck_id: _toggle_ignore_state(did)
    )

    interval_action = submenu.addAction("Set custom interval…")
    interval_action.triggered.connect(
        lambda _checked=False, did=deck_id: _set_custom_interval(did)
    )
