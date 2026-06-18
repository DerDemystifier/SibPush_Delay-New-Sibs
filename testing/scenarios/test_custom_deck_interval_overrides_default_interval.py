from __future__ import annotations

from importlib import import_module

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_addon_owned,
    assert_card_is_not_addon_owned,
    assert_card_queues,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_custom_deck_interval_overrides_default_interval() -> None:
    """
    Scenario: Case when one deck has a custom interval threshold and another deck still relies on
    the default interval.

    The addon should use the deck-specific interval for the custom deck while continuing to apply
    the default threshold everywhere else.
    """
    with temporary_collection() as col:
        model = build_test_notetype(col)

        default_deck_id = make_test_deck_id(col)
        custom_deck_id = col.decks.id("Custom Interval Deck")
        assert custom_deck_id is not None

        custom_note, custom_cards = add_note_with_siblings(
            col, model, custom_deck_id, "Custom interval note"
        )
        default_note, default_cards = add_note_with_siblings(
            col, model, default_deck_id, "Default interval note"
        )

        set_review_card_state(col, custom_cards[0], ivl=20)
        set_review_card_state(col, default_cards[0], ivl=20)

        print(
            "Before processing the custom and default decks, both notes have the same review interval but only one deck will use a custom threshold."
        )
        print_collection_state(col, "Before processing (custom interval vs default interval)")

        with patched_addon_state(col) as patched_addon:
            state_module = import_module(f"{patched_addon.__name__}.sibpush.state")
            ignored_key = state_module.CONFIG_IGNORED_KEY
            rule = {
                "did": str(custom_deck_id),
                "name": "Custom Interval Deck",
                ignored_key: False,
                "interval": 18,
            }
            patched_addon.config_settings["custom_deck_rules"] = [rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(custom_deck_id)] = rule
            patched_addon.ignored_deck_ids[:] = []

            patched_addon.process_all_notes(col)

        print(
            "After processing, the custom deck should treat ivl=20 as mature because its threshold is lower, while the default deck should still suspend its extra siblings."
        )
        print_collection_state(col, "After processing (custom interval wins for the custom deck)")

        assert_card_queues(
            col, custom_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(
            col, default_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_is_not_addon_owned(col, custom_cards[0])
        assert_card_is_not_addon_owned(col, custom_cards[1])
        assert_card_is_addon_owned(col, custom_cards[2])
        assert_card_is_not_addon_owned(col, default_cards[0])
        assert_card_is_addon_owned(col, default_cards[1])
        assert_card_is_addon_owned(col, default_cards[2])


if __name__ == "__main__":
    test_custom_deck_interval_overrides_default_interval()
