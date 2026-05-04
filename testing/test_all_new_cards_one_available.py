from __future__ import annotations

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED


def test_start_work_keeps_one_card_available_for_a_fresh_three_card_note() -> None:
    """
    Scenario: 3 cards are new in a single note.

    This test verifies that start_work() leaves one card available as a NEW card
    and suspends the other two new cards.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Fresh note")

        print_collection_state(col, "Before processing (Fresh 3-card note)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print_collection_state(col, "After processing (One available, two suspended)")

        assert_card_queues(col, cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_start_work_keeps_one_card_available_for_a_fresh_three_card_note()
