from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED


def test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes() -> None:
    """
    Scenario: Case when a four-card note is already tagged by the addon and has two review cards
    plus two suspended siblings.

    The addon should unsuspend the next sibling as a normal new card when processing all notes,
    while leaving the final sibling suspended so only one extra card becomes available.
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
            "Before processing the tagged four-card note: two cards are in review and the two remaining siblings are suspended."
        )
        print_collection_state(col, "Before processing (tagged four-card note)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the next suspended sibling is restored to New, while the last sibling stays suspended and the tag remains in place."
        )
        print_collection_state(col, "After processing (next sibling restored)")

        assert_card_queues(
            col,
            cards,
            [QUEUE_TYPE_REV, QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED],
        )
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes()
