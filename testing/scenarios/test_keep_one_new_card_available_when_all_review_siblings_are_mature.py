from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import (
    QUEUE_TYPE_REV,
    QUEUE_TYPE_NEW,
    QUEUE_TYPE_SUSPENDED,
)


def test_keeps_one_new_card_available_when_all_review_siblings_are_mature() -> None:
    """
    Scenario: Case when a note already has a mature review sibling and two remaining new siblings.

    The addon should leave exactly one new card available for study, keep the mature review card
    in review, and suspend the extra new sibling so the note only exposes one new card at a time.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Mature note")
        set_review_card_state(col, cards[0], ivl=30)

        print(
            "Before processing a note whose review sibling is already mature: one card is in review and two cards are still new."
        )
        print_collection_state(col, "Before processing (mature review sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing the note, one new card stays available, the mature review card remains in review, and the extra sibling is suspended."
        )
        print_collection_state(
            col, "After processing (one new card kept available, extra sibling suspended)"
        )

        assert_card_queues(
            col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_keeps_one_new_card_available_when_all_review_siblings_are_mature()
