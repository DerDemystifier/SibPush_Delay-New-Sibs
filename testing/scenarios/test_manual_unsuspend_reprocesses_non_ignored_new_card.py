from __future__ import annotations

from ..addon_utils import patched_addon_state
from ..card_utils import assert_card_queues
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED


def test_manual_unsuspend_of_non_ignored_new_card_is_reprocessed_and_suspended_again() -> None:
    """
    Scenario: Case when a user manually unsuspends a new card that was suspended by the add-on.

    The add-on should treat the card as a reintroduced new sibling, process it again, and re-suspend
    it.
    """
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Manual unsuspend")

        print("Before initial processing: all sibling cards are new and unmanaged.")
        print_collection_state(col, "Before initial processing")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)
            print(
                "After initial processing: one new card remains available and the trailing siblings are suspended by the add-on."
            )
            print_collection_state(col, "After initial processing")

            # Simulate the user manually unsuspending a new sibling.
            col.sched.unsuspend_cards([cards[1].id])

            print(
                "After manual unsuspend: the trailing sibling is active again, and its custom-data state has been reset by Anki."
            )
            print_collection_state(col, "After manual unsuspend")

            patched_addon.process_all_notes(col)

            print(
                "After reprocessing: the manually unsuspended sibling should be treated as a new sibling again and suspended by the add-on."
            )
            print_collection_state(col, "After reprocessing")

            assert_card_queues(col, [cards[0], cards[2]], [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED])


if __name__ == "__main__":
    test_manual_unsuspend_of_non_ignored_new_card_is_reprocessed_and_suspended_again()
