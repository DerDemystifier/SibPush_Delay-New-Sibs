from __future__ import annotations

from importlib import import_module

from anki.consts import QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_ignored,
    assert_card_is_not_ignored,
    assert_card_queues,
    card_custom_data,
    set_card_custom_data,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id


class _FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.checkable = False
        self.checked = False
        self.triggered = _FakeSignal()

    def setCheckable(self, value: bool) -> None:
        self.checkable = value

    def setChecked(self, value: bool) -> None:
        self.checked = value


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


class _FakeBrowserModel:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


class _FakeBrowser:
    def __init__(self, card_ids: list[int]) -> None:
        self._card_ids = card_ids
        self.model = _FakeBrowserModel()

    def selectedCards(self) -> list[int]:
        return list(self._card_ids)


def test_card_browser_ignore_toggle_round_trip() -> None:
    """The card browser submenu should ignore and un-ignore selected cards in place."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "Browser ignore toggle note")
        third_party_key = "tp"

        set_review_card_state(col, cards[0], ivl=10)

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)
            browser_actions = import_module(f"{patched_addon.__name__}.sibpush.ui.browser_actions")
            state_module = import_module(f"{patched_addon.__name__}.sibpush.state")

            # Add some third-party custom data after SibPush has done its own bookkeeping so we
            # can verify the browser toggle preserves unrelated keys.
            for index, card in enumerate(cards, start=1):
                set_card_custom_data(col, card, {third_party_key: f"card-{index}"})

            browser = _FakeBrowser([card.id for card in cards])
            menu = _FakeMenu("root")
            browser_actions.add_browser_card_actions(browser, menu)

            assert menu.submenus[0].title == "SibPush"
            ignore_action = menu.submenus[0].actions[0]
            assert ignore_action.text == "Ignore cards"
            assert ignore_action.checkable is True
            assert ignore_action.checked is False

            ignore_action.triggered.callbacks[0]()

            assert browser.model.reset_calls == 1
            assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
            for card in cards:
                assert_card_is_ignored(col, card)
                assert card_custom_data(col, card)[third_party_key] == f"card-{cards.index(card) + 1}"
                assert card_custom_data(col, card)[state_module.ADDON_CUSTOM_DATA_KEY] == state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE

            refreshed_menu = _FakeMenu("root")
            browser_actions.add_browser_card_actions(browser, refreshed_menu)
            refreshed_action = refreshed_menu.submenus[0].actions[0]
            assert refreshed_action.checked is True

            refreshed_action.triggered.callbacks[0]()

            assert browser.model.reset_calls == 2
            assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
            for card in cards:
                assert_card_is_not_ignored(col, card)
                assert card_custom_data(col, card)[third_party_key] == f"card-{cards.index(card) + 1}"
                assert state_module.ADDON_CUSTOM_DATA_KEY not in card_custom_data(col, card)


def test_card_browser_ignore_toggle_preserves_manual_suspension() -> None:
    """Ignoring any suspended card should not change its suspension state."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, review_cards = add_note_with_siblings(col, model, deck_id, "Suspended review note")
        set_review_card_state(col, review_cards[0], ivl=10)
        col.sched.suspend_cards([review_cards[0].id])

        _, new_sibling_cards = add_note_with_siblings(
            col, model, deck_id, "Suspended new sibling note"
        )
        col.sched.suspend_cards([new_sibling_cards[0].id])

        single_card_model = build_test_notetype(col, card_count=1)
        _, single_cards = add_note_with_siblings(
            col,
            single_card_model,
            deck_id,
            "Suspended standalone note",
            expected_card_count=1,
        )
        col.sched.suspend_cards([single_cards[0].id])

        with patched_addon_state(col) as patched_addon:
            browser_actions = import_module(f"{patched_addon.__name__}.sibpush.ui.browser_actions")

            for card in (review_cards[0], new_sibling_cards[0], single_cards[0]):
                browser = _FakeBrowser([card.id])
                menu = _FakeMenu("root")
                browser_actions.add_browser_card_actions(browser, menu)

                ignore_action = menu.submenus[0].actions[0]
                assert ignore_action.text == "Ignore card"
                assert ignore_action.checked is False

                ignore_action.triggered.callbacks[0]()

                assert_card_queues(col, [card], [QUEUE_TYPE_SUSPENDED])
                assert_card_is_ignored(col, card)


if __name__ == "__main__":
    test_card_browser_ignore_toggle_round_trip()
