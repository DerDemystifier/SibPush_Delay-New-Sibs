from __future__ import annotations

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_not_ignored,
    assert_card_queues,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_process_all_notes_restores_the_last_sibling_after_suspension() -> None:
    """
    Scenario: Case when a note only has one suspended new sibling left.

    The addon should restore that sibling to New because the note no longer has any constraints
    that justify keeping it suspended.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=2)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Single suspended sibling",
            expected_card_count=2,
        )

        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])

        print(
            "Before processing the two-card note: one card is in review and the last new sibling is suspended."
        )
        print_collection_state(col, "Before processing (last suspended sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the last new sibling is restored to New."
        )
        print_collection_state(col, "After processing (last suspended sibling restored)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, cards[1])


def test_reviewer_hook_buries_the_last_sibling_after_restoring_it() -> None:
    """
    Scenario: Case when the reviewer hook restores the last suspended sibling and buries it for
    the current day.

    The addon should bury the sibling for the day when the reviewer hook is involved.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=2)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Buried last sibling",
            expected_card_count=2,
        )

        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])

        print(
            "Before reviewer-hook processing the two-card note: one card is in review and the last new sibling is suspended."
        )
        print_collection_state(col, "Before reviewer-hook processing (last suspended sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_note(col, note.id, coming_from_reviewer_hook=True)

        print(
            "After reviewer-hook processing, the last sibling is buried for today."
        )
        print_collection_state(col, "After reviewer-hook processing (last sibling buried)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED])
        assert_card_is_not_ignored(col, cards[1])


if __name__ == "__main__":
    test_process_all_notes_restores_the_last_sibling_after_suspension()
    test_reviewer_hook_buries_the_last_sibling_after_restoring_it()
