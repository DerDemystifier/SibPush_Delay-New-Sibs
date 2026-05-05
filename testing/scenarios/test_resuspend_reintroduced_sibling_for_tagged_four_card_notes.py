from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED


def test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes() -> None:
    """
    Scenario: Case when a tagged four-card note already has one active new sibling and a later
    sibling was manually (maybe accidentally) unsuspended by the user.

    The addon should leave the first new sibling available, but it should suspend the manually
    reintroduced trailing sibling again so the note returns to its managed state.
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
        col.sched.suspend_cards([cards[2].id, cards[3].id])
        note.add_tag(addon.SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

        # Simulate a user accidentally unsuspending a sibling that should have stayed hidden.
        col.sched.unsuspend_cards([cards[3].id])

        print(
            "Before processing the tagged four-card note: one card is in review, one new sibling is active, and a later sibling was accidentally unsuspended."
        )
        print_collection_state(col, "Before processing (reintroduced tagged sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the addon keeps the first new sibling available and re-suspends the later sibling that was manually brought back."
        )
        print_collection_state(col, "After processing (reintroduced tagged sibling)")

        assert_card_queues(
            col,
            cards,
            [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED],
        )
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes()
