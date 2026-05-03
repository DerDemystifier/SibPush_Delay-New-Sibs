from __future__ import annotations

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state


def test_leaves_pre_suspended_cards_untouched() -> None:
    """
    Scenario: All sibling cards are already suspended by the user.

    This test verifies that if all three sibling cards are already suspended by the user
    before the addon runs, the addon does not touch them or change their queue state and does
    not add the SibPush-suspended tag to the note.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(col, model, deck_id, "Already suspended note")

        col.sched.suspend_cards([card.id for card in cards])

        print_collection_state(col, "Before processing (Already suspended)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.start_work(col)

        print_collection_state(col, "After processing (Already suspended)")

        assert_card_queues(col, cards, [-1, -1, -1])
        print(f"Note tags after processing: {col.get_note(note.id).tags} .. should NOT include {addon.SUSPENDED_BY_ADDON_TAG} as the cards were already suspended by the user and so remain untouched.")
        assert not col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_leaves_pre_suspended_cards_untouched()
