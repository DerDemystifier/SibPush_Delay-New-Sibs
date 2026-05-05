from __future__ import annotations

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED


def test_process_note_only_updates_the_target_note_from_reviewer_hook() -> None:
    """
    Scenario: Case when the reviewer hook processes one note while another note in the same
    collection should remain untouched.

    The addon should update only the requested note, leave the control note alone, and preserve the
    reviewer-hook behavior that buries the next sibling instead of exposing it immediately.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        target_note, target_cards = add_note_with_siblings(col, model, deck_id, "Target note")
        control_note, control_cards = add_note_with_siblings(col, model, deck_id, "Control note")

        set_review_card_state(col, target_cards[0], ivl=30)
        set_review_card_state(col, control_cards[0], ivl=30)

        print(
            "Before processing the note of a card that was just reviewed and matured: the target note and the control note both still have one review card and two new siblings."
        )
        print_collection_state(col, "Before processing single note (target vs control)")

        with patched_addon_state(col) as patched_addon:
            assert patched_addon.last_checked_state is None
            patched_addon.process_note(col, target_note.id, coming_from_reviewer_hook=True)
            assert patched_addon.last_checked_state is None

        print(
            "After processing the note, the next card is buried until tomorrow, and the other cards from the same note are suspended. The remaining notes stay unprocessed."
        )
        print_collection_state(col, "After processing single note (target updated, control untouched)")

        assert_card_queues(
            col, target_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(col, control_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert col.get_note(target_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert not col.get_note(control_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_note_only_updates_the_target_note_from_reviewer_hook()
