"""Deck-browser actions for managing SibPush per-deck rules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

import aqt
from aqt.qt import QInputDialog, QMenu

from ..config.parser import get_custom_deck_rule_snapshot, update_custom_deck_rule
from ..state import ADDON_CUSTOM_DATA_IGNORED_VALUE, ADDON_CUSTOM_DATA_KEY, CONFIG_IGNORED_KEY, get_mw


def _get_collection() -> Any | None:
    """Return the active collection, if Anki is ready.

    Returns:
        Any | None: The Anki collection object, or None if Anki is not running or the collection is not loaded.
    """

    current_mw = get_mw()
    if current_mw is None:
        return None

    return getattr(current_mw, "col", None)


def _add_action(menu: QMenu, label: str, handler: Callable[[int], None], deck_id: int) -> None:
    """Add a deck action and connect it to the supplied handler."""

    action: Any = cast(Any, menu).addAction(label)
    if action is not None:
        action.triggered.connect(lambda _checked=False, did=deck_id: handler(did))  # type: ignore[union-attr]


def _get_deck_name(col: Any, deck_id: int) -> str:
    """Return the readable deck name for a deck id.

    Args:
        col (Any): The Anki collection object.
        deck_id (int): The deck identifier.

    Returns:
        str: The human-readable deck name, or the deck ID as a string if the name cannot be found.
    """

    deck = col.decks.get(deck_id)
    if isinstance(deck, Mapping):
        name = cast(Any, deck).get("name", deck_id)
        return str(name or deck_id).strip() or str(deck_id)

    return str(deck_id)


def _toggle_ignore_state(deck_id: int) -> None:
    """Flip the ignore state for one deck.

    This function toggles whether a deck is ignored by the add-on. When a deck
    is ignored, the add-on will not manage sibling card suspension for that deck.

    Args:
        deck_id (int): The deck identifier to toggle.

    Returns:
        None: The configuration is updated as a side effect.
    """

    col = _get_collection()
    if col is None:
        return

    deck_name = _get_deck_name(col, deck_id)
    snapshot = get_custom_deck_rule_snapshot(str(deck_id))
    update_custom_deck_rule(
        str(deck_id),
        deck_name,
        ignored=not snapshot[CONFIG_IGNORED_KEY],
        interval=snapshot["interval"],
    )


def _set_custom_interval(deck_id: int) -> None:
    """Prompt for and save a custom interval for one deck.

    This function displays a dialog prompting the user to enter a custom
    maturity interval (in days) for the specified deck. The interval determines
    when sibling cards are considered "mature" and can be unsuspended.

    Args:
        deck_id (int): The deck identifier to configure.

    Returns:
        None: The configuration is updated if the user accepts the dialog.
    """

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
        ignored=snapshot[CONFIG_IGNORED_KEY],
        interval=value,
    )


def _show_ignored_cards_in_browser(deck_id: int) -> None:
    """Open the card browser pre-filled with a search for ignored cards in one deck.

    This function is called when the user selects "Show ignored cards" from the
    SibPush deck submenu. It opens (or focuses) the Anki card browser with a search
    query that finds cards in the given deck that SibPush has marked as ignored.

    Args:
        deck_id (int): The deck identifier whose ignored cards should be shown.

    Returns:
        None: The browser window is opened as a side effect.
    """

    col = _get_collection()
    if col is None:
        return

    deck_name = _get_deck_name(col, deck_id)
    query = f'deck:"{deck_name}" prop:cds:{ADDON_CUSTOM_DATA_KEY}={ADDON_CUSTOM_DATA_IGNORED_VALUE}'

    current_mw = get_mw()
    if current_mw is None:
        return

    aqt.dialogs.open("Browser", current_mw, search=(query,))


def add_deck_actions_to_options_menu(menu: QMenu, deck_id: int) -> None:
    """Add the SibPush submenu to the deck browser options menu.

    This function is called by Anki's deck browser when the user right-clicks on a deck.
    It adds a "SibPush" submenu with three options:
    - Toggle the ignore state (ignore/unignore the deck)
    - Set a custom maturity interval for the deck
    - Open the card browser to show cards ignored by SibPush in this deck

    Args:
        menu (QMenu): The Qt menu widget to add items to.
        deck_id (int): The identifier of the deck being right-clicked.

    Returns:
        None: Menu items are added as a side effect.
    """

    if deck_id is None:  # type: ignore[unreachable]
        return

    col = _get_collection()
    if col is None:
        return

    snapshot = get_custom_deck_rule_snapshot(str(deck_id))
    submenu = menu.addMenu("SibPush")
    if submenu is None:
        return

    # Add the ignore/unignore toggle action
    ignore_label = "Unignore current deck" if snapshot[CONFIG_IGNORED_KEY] else "Ignore current deck"
    _add_action(submenu, ignore_label, _toggle_ignore_state, deck_id)

    # Add the custom interval configuration action
    _add_action(submenu, "Set custom interval…", _set_custom_interval, deck_id)

    # Add an action to search the browser for cards ignored by SibPush in this deck
    _add_action(submenu, "Show ignored cards…", _show_ignored_cards_in_browser, deck_id)
