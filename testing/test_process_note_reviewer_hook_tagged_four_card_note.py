from __future__ import annotations

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues, set_review_card_state
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED


def test_process_note_buries_the_third_card_when_called_from_reviewer_hook() -> None:
    """
    Scenario: One note has 4 cards and is already managed by the addon.

    Initial state:
    - Card 1: Review, ivl=60
    - Card 2: Review, ivl=30
    - Card 3: Suspended new card
    - Card 4: Suspended new card

    When process_note(..., coming_from_reviewer_hook=True) runs, the first suspended
    new card should be unsuspended and buried so it is not reviewed immediately.
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

        print_collection_state(col, "Before reviewer-hook processing (tagged four-card note)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_note(col, note.id, coming_from_reviewer_hook=True)

        print_collection_state(col, "After reviewer-hook processing (third card should be buried)")

        assert_card_queues(
            col,
            cards,
            [QUEUE_TYPE_REV, QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED],
        )
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_note_buries_the_third_card_when_called_from_reviewer_hook()
