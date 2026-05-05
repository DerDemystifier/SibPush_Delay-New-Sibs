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


def test_suspends_new_siblings_when_an_immature_review_card_exists() -> None:
    """
    Scenario: Case when one note has an immature review card while another note in the same deck
    has a mature review card.

    The addon should suspend the new siblings for the immature note, but it should leave one new
    sibling available for the mature control note so the two notes demonstrate opposite outcomes.
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        target_note, target_cards = add_note_with_siblings(col, model, deck_id, "Target note")
        control_note, control_cards = add_note_with_siblings(col, model, deck_id, "Control note")

        set_review_card_state(col, target_cards[0], ivl=10)
        set_review_card_state(col, control_cards[0], ivl=30)

        print(
            "Before processing the notes, the target note has an immature review card and the control note has a mature review card."
        )
        print_collection_state(col, "Before processing (immature target vs mature control)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the target note keeps the review card but suspends its new siblings, while the control note keeps one new sibling available."
        )
        print_collection_state(col, "After processing (immature target vs mature control)")

        assert_card_queues(
            col, target_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert_card_queues(
            col, control_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(target_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert col.get_note(control_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_suspends_new_siblings_when_an_immature_review_card_exists()
