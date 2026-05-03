from __future__ import annotations

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues, set_review_card_state
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state


def test_start_work_leaves_one_new_card_active_when_all_siblings_are_mature() -> None:
    """
    Scenario: All Siblings are Mature

    This test verifies that if all existing cards for a note are 'mature'
    (interval >= 21) or there are no review cards yet, the addon will:
    1. Identify all 'new' cards for the note.
    2. Leave EXACTLY ONE new card as 'New' (active).
    3. Suspend all other 'new' cards.

    Expected Result: One new card remains available; others are pushed back.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Mature note")
        set_review_card_state(col, cards[0], ivl=30)

        print_collection_state(col, "Before processing (Mature Siblings)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.start_work(col)

        print_collection_state(col, "After processing (One New Card left active)")

        assert_card_queues(col, cards, [2, 0, -1])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


def run() -> None:
    print("\n\n")
    print("[↓Running↓] test_start_work_leaves_one_new_card_active_when_all_siblings_are_mature")
    test_start_work_leaves_one_new_card_active_when_all_siblings_are_mature()
    print("[↑OK↑] test_start_work_leaves_one_new_card_active_when_all_siblings_are_mature")


if __name__ == "__main__":
    run()
