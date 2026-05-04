from __future__ import annotations

from testing.print_utils import print_collection_state

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues, set_review_card_state
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from anki.consts import (
    QUEUE_TYPE_NEW,
    QUEUE_TYPE_REV,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
)


def test_process_single_note_while_reviewing() -> None:
    """
    Scenario: Process one note directly.

    This regression test mirrors the reviewer hook path: processing one note should
    not touch other notes and should not update the batch cache used by process_all_notes().
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        target_note, target_cards = add_note_with_siblings(col, model, deck_id, "Target note")
        control_note, control_cards = add_note_with_siblings(col, model, deck_id, "Control note")

        set_review_card_state(col, target_cards[0], ivl=30)
        set_review_card_state(col, control_cards[0], ivl=30)

        print_collection_state(col, "Before processing single note")

        with patched_addon_state(col) as patched_addon:
            assert patched_addon.last_checked_state is None
            patched_addon.process_note(col, target_note.id, coming_from_reviewer_hook=True)
            assert patched_addon.last_checked_state is None

        print_collection_state(col, "After reviewing ONLY the first note")

        assert_card_queues(
            col, target_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(col, control_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert col.get_note(target_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert not col.get_note(control_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_single_note_while_reviewing()
