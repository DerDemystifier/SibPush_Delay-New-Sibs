from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED


def test_keeps_one_new_card_available_for_a_fresh_three_card_note() -> None:
    """
    Scenario: Case when a note starts with three fresh new cards and no review history.

    The addon should keep one new card available for study and suspend the other two new siblings,
    proving that the start-of-work behavior still limits the note to a single active new card.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Fresh note")

        print(
            "Before processing a fresh three-card note: all cards are still new and none of them has been filtered yet."
        )
        print_collection_state(col, "Before processing (fresh three-card note)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, one new card remains available and the other two siblings are suspended for later."
        )
        print_collection_state(col, "After processing (one new card available)")

        assert_card_queues(col, cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_keeps_one_new_card_available_for_a_fresh_three_card_note()
