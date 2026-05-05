from __future__ import annotations

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_process_all_notes_removes_the_suspension_tag_after_restoring_the_last_sibling() -> None:
    """
    Scenario: Case when a tagged note only has one suspended new sibling left.

    The addon should restore that sibling to New and clear its suspension tag because the note no
    longer has any suspended cards.
    """

    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col, card_count=2)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Single suspended sibling",
            expected_card_count=2,
        )

        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])
        note.add_tag(addon.SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

        print(
            "Before processing the tagged two-card note: one card is in review and the last new sibling is suspended."
        )
        print_collection_state(col, "Before processing (last suspended sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_all_notes(col)

        print(
            "After processing, the last new sibling is restored to New and the stale suspension tag is removed."
        )
        print_collection_state(col, "After processing (last suspended sibling restored)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW])
        assert not col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


def test_reviewer_hook_removes_the_suspension_tag_after_burying_the_last_sibling() -> None:
    """
    Scenario: Case when the reviewer hook restores the last suspended sibling and buries it for
    the current day.

    The addon should bury the sibling for the day, but once no suspended cards remain, the
    suspension tag should be cleared.
    """

    with temporary_collection() as col:
        addon = load_addon_module()
        model = build_test_notetype(col, card_count=2)
        deck_id = make_test_deck_id(col)

        note, cards = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Buried last sibling",
            expected_card_count=2,
        )

        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])
        note.add_tag(addon.SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

        print(
            "Before reviewer-hook processing the tagged two-card note: one card is in review and the last new sibling is suspended."
        )
        print_collection_state(col, "Before reviewer-hook processing (last suspended sibling)")

        with patched_addon_state(col) as patched_addon:
            patched_addon.process_note(col, note.id, coming_from_reviewer_hook=True)

        print(
            "After reviewer-hook processing, the last sibling is buried for today and the stale suspension tag is removed."
        )
        print_collection_state(col, "After reviewer-hook processing (last sibling buried)")

        assert_card_queues(col, cards, [QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED])
        assert not col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


if __name__ == "__main__":
    test_process_all_notes_removes_the_suspension_tag_after_restoring_the_last_sibling()
    test_reviewer_hook_removes_the_suspension_tag_after_burying_the_last_sibling()
