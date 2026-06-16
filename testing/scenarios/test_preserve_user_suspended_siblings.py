from __future__ import annotations

from ..addon_utils import patched_addon_state
from ..card_utils import assert_card_is_not_addon_owned, assert_card_queues
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_SUSPENDED


def test_preserves_user_suspended_siblings_without_retagging() -> None:
    """
    Scenario: Case when every sibling card on a note was already suspended by the user.

    The addon should leave the card queues unchanged and should not claim ownership of any card,
    because the cards were already out of circulation before the addon ran.
    """
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Already suspended note")

        col.sched.suspend_cards([card.id for card in cards])

        print(
            "Before processing already suspended siblings: all cards are suspended by the user and the addon has not claimed ownership."
        )
        print_collection_state(col, "Before processing (already suspended siblings)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the queues stay exactly the same, and the note should still have no SibPush-owned cards."
        )
        print_collection_state(col, "After processing (already suspended siblings)")

        assert_card_queues(
            col, cards, [QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        for card in cards:
            assert_card_is_not_addon_owned(col, card)


if __name__ == "__main__":
    test_preserves_user_suspended_siblings_without_retagging()
