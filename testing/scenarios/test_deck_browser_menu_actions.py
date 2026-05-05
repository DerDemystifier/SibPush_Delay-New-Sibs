from __future__ import annotations

from importlib import import_module
from unittest.mock import patch

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..collection_utils import temporary_collection
from ..note_utils import make_test_deck_id


class _FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = _FakeSignal()


class _FakeMenu:
    def __init__(self, title: str | None = None) -> None:
        self.title = title
        self.actions: list[_FakeAction] = []
        self.submenus: list[_FakeMenu] = []

    def addMenu(self, title: str) -> _FakeMenu:
        submenu = _FakeMenu(title)
        self.submenus.append(submenu)
        return submenu

    def addAction(self, text: str) -> _FakeAction:
        action = _FakeAction(text)
        self.actions.append(action)
        return action


def test_deck_browser_submenu_toggles_ignore_and_sets_interval() -> None:
    """
    Scenario: Case when the deck browser options menu exposes the SibPush submenu.

    The submenu should show toggle and interval actions, and both actions should persist a config
    save when triggered.
    """

    with temporary_collection() as col:
        deck_id = make_test_deck_id(col)
        fake_manager = FakeAddonManager(
            {
                "default_interval": 21,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            deck_actions = import_module(f"{addon.__name__}.sibpush.ui.deck_actions")

            menu = _FakeMenu("root")
            deck_actions.add_deck_actions_to_options_menu(menu, deck_id)

            assert menu.submenus, "The SibPush submenu should be added to the deck browser menu."
            submenu = menu.submenus[0]
            assert submenu.title == "SibPush"
            assert [action.text for action in submenu.actions] == [
                "Ignore current deck",
                "Set custom interval…",
            ]

            submenu.actions[0].triggered.callbacks[0]()
            assert fake_manager.writes[-1]["custom_deck_rules"][0]["did"] == str(deck_id)
            assert fake_manager.writes[-1]["custom_deck_rules"][0]["ignored"] is True

            refreshed_menu = _FakeMenu("root")
            deck_actions.add_deck_actions_to_options_menu(refreshed_menu, deck_id)
            assert refreshed_menu.submenus[0].actions[0].text == "Unignore current deck"

            with patch.object(deck_actions.QInputDialog, "getInt", return_value=(33, True)):
                refreshed_menu.submenus[0].actions[1].triggered.callbacks[0]()

            assert fake_manager.writes[-1]["custom_deck_rules"][0]["interval"] == 33
            assert fake_manager.writes[-1]["custom_deck_rules"][0]["ignored"] is True


if __name__ == "__main__":
    test_deck_browser_submenu_toggles_ignore_and_sets_interval()
