from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED


def test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes() -> None:
    """
    Scenario: Case when the reviewer hook processes a tagged four-card note whose next sibling
    should not appear immediately.

    The addon should unsuspend the next sibling and bury it for the current day, which keeps the
    newly revealed card hidden from immediate review while leaving the final sibling suspended.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col, card_count=4)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Tagged four-card note",
            expected_card_count=4,
        )

        set_review_card_state(col, cards[0], ivl=60)
        set_review_card_state(col, cards[1], ivl=30)
        col.sched.suspend_cards([cards[2].id, cards[3].id])
        note.add_tag(addon.SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

        print(
            "Before reviewer-hook processing the tagged four-card note: the first two cards are in review and the other two siblings are suspended."
        )
        print_collection_state(col, "Before reviewer-hook processing (tagged four-card note)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_note(col, note.id, coming_from_reviewer_hook=True)

        print(
            "After reviewer-hook processing, the next sibling is buried until tomorrow, and the final sibling remains suspended."
        )
        print_collection_state(col, "After reviewer-hook processing (next sibling buried)")

        assert_card_queues(
            col,
            cards,
            [QUEUE_TYPE_REV, QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED],
        )
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes()
