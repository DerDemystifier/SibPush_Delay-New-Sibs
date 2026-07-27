from __future__ import annotations

import json
from importlib import import_module
from unittest.mock import patch

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_ignored,
    assert_card_is_not_ignored,
    assert_card_is_not_suspended_by_addon,
    assert_card_is_suspended_by_addon,
    assert_card_queues,
    card_custom_data,
    set_card_custom_data,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck() -> None:
    """
    Scenario: Case when a deck that already has add-on-suspended cards becomes ignored.

    The config save hook should undo the add-on's suspension work for that deck instead of simply
    leaving the cards suspended and excluding the deck from future processing.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Ignored deck cleanup note")
        set_review_card_state(col, cards[0], ivl=10)

        print(
            "Before processing, the note has an immature review sibling, so all new siblings should be suspended by the add-on."
        )
        print_collection_state(col, "Before processing (will become ignored later)")

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            ignored_key = state_module.CONFIG_IGNORED_KEY
            active_rule = {
                "did": str(deck_id),
                "name": "Ignored deck cleanup note",
                ignored_key: False,
                "interval": 21,
            }
            patched_addon.config_settings["custom_deck_rules"] = [active_rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(deck_id)] = active_rule
            patched_addon.ignored_deck_ids[:] = []

            patched_addon.process_all_notes(col)

            print("After processing, the add-on has suspended and marked the new siblings.")
            print_collection_state(col, "After processing (suspended by add-on)")

            assert_card_queues(
                col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert_card_is_not_ignored(col, cards[0])
            assert_card_is_suspended_by_addon(col, cards[1])
            assert_card_is_suspended_by_addon(col, cards[2])

            ignored_rule = {
                "did": str(deck_id),
                "name": "Ignored deck cleanup note",
                ignored_key: True,
                "interval": 21,
            }
            config_text = json.dumps(
                {
                    "debug": False,
                    "default_interval": 30,
                    "custom_deck_rules": [ignored_rule],
                    "tag_rules": {},
                }
            )

            parser_module.on_config_save(config_text, addon.__name__)

            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [str(deck_id)],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }

        print(
            "After the deck becomes ignored, the add-on should keep the cards suspended until the browser render consumes the queued cleanup."
        )
        print_collection_state(col, "After config save (cleanup queued, not yet run)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
        assert_card_is_not_ignored(col, cards[0])
        assert_card_is_not_ignored(col, cards[1])
        assert_card_is_not_ignored(col, cards[2])


def test_unsuspend_all_addon_cards_in_deck_restores_only_owned_new_cards() -> None:
    """Deck restore should unsuspend only currently suspended, marker-owned new cards."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Deck restore note")
        set_review_card_state(col, cards[0], ivl=10)

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            suspension_module = import_module(f"{addon.__name__}.sibpush.processing.suspension")

            patched_addon.process_all_notes(col)

            ignored_rule = {
                "did": str(deck_id),
                "name": "Deck restore note",
                state_module.CONFIG_IGNORED_KEY: True,
                "interval": 30,
            }
            patched_addon.custom_deck_rules_by_did[str(deck_id)] = ignored_rule

            manual_note, manual_cards = add_note_with_siblings(
                col, model, deck_id, "Manual deck suspension note"
            )
            col.sched.suspend_cards([manual_cards[1].id])

            ignored_note, ignored_cards = add_note_with_siblings(
                col, model, deck_id, "Ignored deck suspension note"
            )

            review_note, review_cards = add_note_with_siblings(
                col, model, deck_id, "Manual review deck suspension note"
            )
            set_review_card_state(col, review_cards[0], ivl=10)

            single_card_model = build_test_notetype(col, card_count=1)
            single_card_note, single_card_cards = add_note_with_siblings(
                col, single_card_model, deck_id, "Manually suspended single-card note", expected_card_count=1
            )
            col.sched.suspend_cards([single_card_cards[0].id])

            set_card_custom_data(
                col,
                ignored_cards[2],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            col.sched.suspend_cards([ignored_cards[2].id])

            assert_card_is_suspended_by_addon(col, cards[1])
            assert_card_is_suspended_by_addon(col, cards[2])
            assert_card_is_not_suspended_by_addon(col, manual_cards[1])

            with patch.object(suspension_module, "tooltip"):
                suspension_module.unsuspend_all_addon_cards_in_deck(col, str(deck_id))

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, manual_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_NEW])
        assert_card_queues(col, single_card_cards, [QUEUE_TYPE_SUSPENDED])
        assert_card_queues(col, ignored_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED])
        assert_card_queues(col, review_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, manual_cards[1])
        assert_card_is_ignored(col, ignored_cards[2])
        assert_card_is_not_suspended_by_addon(col, manual_cards[1])
        assert_card_is_not_suspended_by_addon(col, ignored_cards[2])
        assert card_custom_data(col, review_cards[0]).get(state_module.ADDON_CUSTOM_DATA_KEY) is None


if __name__ == "__main__":
    test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck()
    test_unsuspend_all_addon_cards_in_deck_restores_only_owned_new_cards()
