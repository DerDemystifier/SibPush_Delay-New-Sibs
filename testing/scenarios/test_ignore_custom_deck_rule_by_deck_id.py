from __future__ import annotations

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_ignores_custom_deck_rule_by_deck_id() -> None:
    """
    Scenario: Case when a custom deck rule is marked ignored and must be matched by deck ID.

    The addon should process the active deck, leave the ignored deck untouched, and prove that the
    ignored-deck check uses the deck identifier instead of relying on the deck name alone.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)

        active_deck_id = make_test_deck_id(col)
        ignored_deck_id = col.decks.id("Ignored Sib Deck")
        assert ignored_deck_id is not None

        active_note, active_cards = add_note_with_siblings(
            col, model, active_deck_id, "Active note"
        )
        ignored_note, ignored_cards = add_note_with_siblings(
            col, model, ignored_deck_id, "Ignored note"
        )

        print(
            "Before processing a deck rule that is ignored by deck ID: both decks still have three fresh new cards."
        )
        print_collection_state(col, "Before processing (deck rule matched by did)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.config_settings["custom_deck_rules"] = [
                {"did": str(ignored_deck_id), "name": "Ignored Sib Deck", "ignored": True}
            ]
            patched_addon.ignored_deck_ids[:] = [str(ignored_deck_id)]
            patched_addon.process_all_notes(col)

        print(
            "After processing, the active deck is filtered as usual while the ignored deck stays completely untouched."
        )
        print_collection_state(col, "After processing (ignored deck left untouched)")

        assert_card_queues(
            col, active_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(col, ignored_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert col.get_note(active_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert not col.get_note(ignored_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_ignores_custom_deck_rule_by_deck_id()
