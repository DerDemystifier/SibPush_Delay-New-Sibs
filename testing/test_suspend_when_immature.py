from __future__ import annotations

from .addon_utils import load_addon_module, patched_addon_state
from .card_utils import assert_card_queues, set_review_card_state
from .collection_utils import temporary_collection
from .note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from .print_utils import print_collection_state
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED


def test_suspend_new_cards_if_immature_sibling_exists() -> None:
    """
    Scenario: Immature Sibling Exists

    This test verifies that if any card from a note is 'immature' (interval < 21),
    all other 'new' cards for that note are suspended.

    Steps:
    1. Create two notes (Target and Control) with 3 cards each.
    2. Set Card 1 of Target Note to Ivl=10 (Immature). Cards 2 & 3 are New.
    3. Set Card 1 of Control Note to Ivl=30 (Mature). Cards 2 & 3 are New.
    4. Run addon logic.

    Expected:
    - Target Note: Card 1 (Review), Card 2 (Suspended), Card 3 (Suspended).
    - Control Note: Card 1 (Review), Card 2 (New), Card 3 (Suspended).
    """
    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        target_note, target_cards = add_note_with_siblings(col, model, deck_id, "Target note")
        control_note, control_cards = add_note_with_siblings(col, model, deck_id, "Control note")

        set_review_card_state(col, target_cards[0], ivl=10)
        set_review_card_state(col, control_cards[0], ivl=30)

        print_collection_state(col, "Before processing (Immature vs Mature)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.start_work(col)

        print_collection_state(col, "After processing (Immature vs Mature)")

        assert_card_queues(col, target_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
        assert_card_queues(col, control_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED])
        assert col.get_note(target_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert col.get_note(control_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_suspend_new_cards_if_immature_sibling_exists()
