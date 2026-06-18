"""Card-browser actions for the SibPush add-on."""

from __future__ import annotations

from aqt.browser.browser import Browser
from typing import Any

from aqt.qt import QMenu

from ..processing.suspension import card_is_addon_owned
from ..state import get_mw


def add_browser_card_actions(browser: Browser, menu: QMenu) -> None:
    """Add the SibPush placeholder submenu to the card browser context menu.

    Args:
        browser (aqt.browser.Browser): The Anki card browser instance.
        menu (aqt.qt.QMenu): The context menu to extend.

    Returns:
        None: The menu is modified in place.
    """

    card_ids = browser.selectedCards()
    if not card_ids:
        return

    current_mw = get_mw()
    if current_mw is None:
        return
    col = getattr(current_mw, "col", None)
    if col is None:
        return

    cards = [col.get_card(cid) for cid in card_ids]
    all_ignored = all(card_is_addon_owned(card) for card in cards)
    label = "Ignore card" if len(card_ids) == 1 else "Ignore cards"

    submenu: Any = menu.addMenu("SibPush")
    ignore_action: Any = submenu.addAction(label)
    ignore_action.setCheckable(True)
    ignore_action.setChecked(all_ignored)
    ignore_action.triggered.connect(lambda: None)
