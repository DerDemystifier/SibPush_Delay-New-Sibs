from __future__ import annotations

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_addon_owned,
    assert_card_is_not_addon_owned,
    assert_card_queues,
    set_addon_custom_data,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED


def test_process_all_notes_clears_the_ownership_marker_for_a_user_unsuspended_trailing_card() -> None:
    """
    Scenario: Case when a four-card note already has one active new sibling and a later sibling
    was manually unsuspended by the user.

    The addon should leave the first new sibling available, clear the ownership marker from the
    trailing sibling, and leave it active instead of re-suspending it.
    """
    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=4)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Addon-owned four-card note",
            expected_card_count=4,
        )

        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[2].id, cards[3].id])
        set_addon_custom_data(col, cards[2])
        set_addon_custom_data(col, cards[3])

        # Simulate a user accidentally unsuspending a sibling that should have stayed hidden.
        col.sched.unsuspend_cards([cards[3].id])

        print(
            "Before processing the four-card note: one card is in review, one new sibling is active, and a later sibling was accidentally unsuspended."
        )
        print_collection_state(col, "Before processing (reintroduced addon-owned sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the addon keeps the first new sibling available and clears the trailing sibling's ownership marker without re-suspending it."
        )
        print_collection_state(col, "After processing (reintroduced addon-owned sibling)")

        assert_card_queues(
            col,
            cards,
            [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_NEW],
        )
        assert_card_is_not_addon_owned(col, cards[1])
        assert_card_is_addon_owned(col, cards[2])
        assert_card_is_not_addon_owned(col, cards[3])


if __name__ == "__main__":
    test_process_all_notes_clears_the_ownership_marker_for_a_user_unsuspended_trailing_card()