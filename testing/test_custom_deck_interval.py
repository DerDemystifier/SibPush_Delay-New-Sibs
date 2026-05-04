from __future__ import annotations

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues, set_review_card_state
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state


def test_custom_deck_interval_overrides_default_threshold() -> None:
    """A deck-specific interval should override the global default_interval."""

    with temporary_collection() as col:
        addon = load_addon_module()
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

        print_collection_state(col, "Before processing (custom interval vs default)")

        with patched_addon_state(col) as patched_addon:
            rule = {
                "did": str(custom_deck_id),
                "name": "Custom Interval Deck",
                "ignored": False,
                "interval": 18,
            }
            patched_addon.config_settings["custom_deck_rules"] = [rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[str(custom_deck_id)] = rule
            patched_addon.ignored_deck_ids[:] = []

            patched_addon.process_all_notes(col)

        print_collection_state(col, "After processing (custom interval (18d) vs default)")

        assert_card_queues(
            col, custom_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(
            col, default_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(custom_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert col.get_note(default_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_custom_deck_interval_overrides_default_threshold()
