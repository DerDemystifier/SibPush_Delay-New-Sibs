from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_ignored,
    assert_card_is_not_ignored,
    assert_card_queues,
    card_custom_data,
    set_card_custom_data,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype
from ..print_utils import print_collection_state


def test_on_addon_delete_unsuspends_all_non_ignored_new_cards_before_deletion() -> None:
    """Deleting SibPush should restore every suspended new card except ignored ones."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_a_id = col.decks.id("SibPush Delete Deck A")
        deck_b_id = col.decks.id("SibPush Delete Deck B")

        note_a, cards_a = add_note_with_siblings(col, model, deck_a_id, "Delete cleanup note A")
        note_b, cards_b = add_note_with_siblings(col, model, deck_b_id, "Delete cleanup note B")
        set_review_card_state(col, cards_a[0], ivl=10)
        set_review_card_state(col, cards_b[0], ivl=10)

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            patched_addon.process_all_notes(col)

            assert_card_queues(
                col,
                cards_a,
                [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED],
            )
            assert_card_queues(
                col,
                cards_b,
                [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED],
            )
            assert_card_is_not_ignored(col, cards_a[1])
            assert_card_is_not_ignored(col, cards_a[2])
            assert_card_is_not_ignored(col, cards_b[1])
            assert_card_is_not_ignored(col, cards_b[2])

            manual_note, manual_cards = add_note_with_siblings(
                col, model, deck_a_id, "Manually suspended note"
            )
            col.sched.suspend_cards([manual_cards[1].id])

            ignored_note, ignored_cards = add_note_with_siblings(
                col, model, deck_b_id, "Ignored suspended note"
            )

            review_note, review_cards = add_note_with_siblings(
                col, model, deck_b_id, "Manually suspended review note"
            )
            set_review_card_state(col, review_cards[0], ivl=10)

            set_card_custom_data(
                col,
                ignored_cards[2],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            col.sched.suspend_cards([ignored_cards[2].id])

            assert card_custom_data(col, manual_cards[1]).get(state_module.ADDON_CUSTOM_DATA_KEY) is None
            assert card_custom_data(col, ignored_cards[2]).get(state_module.ADDON_CUSTOM_DATA_KEY) == state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE
            assert card_custom_data(col, review_cards[0]).get(state_module.ADDON_CUSTOM_DATA_KEY) is None

            print_collection_state(col, "Before addon deletion (cards are add-on suspended)")

            hooks_module.on_addon_delete(SimpleNamespace(), [addon.__name__])

        print_collection_state(col, "After addon deletion (cards restored immediately)")

        assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, manual_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, ignored_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED])
        assert_card_queues(col, review_cards, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, cards_a[1])
        assert_card_is_not_ignored(col, cards_a[2])
        assert_card_is_not_ignored(col, cards_b[1])
        assert_card_is_not_ignored(col, cards_b[2])
        assert_card_is_not_ignored(col, manual_cards[1])
        assert_card_is_ignored(col, ignored_cards[2])
        assert card_custom_data(col, manual_cards[1]).get(state_module.ADDON_CUSTOM_DATA_KEY) is None
        assert card_custom_data(col, ignored_cards[2]).get(state_module.ADDON_CUSTOM_DATA_KEY) == state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE
        assert card_custom_data(col, review_cards[0]).get(state_module.ADDON_CUSTOM_DATA_KEY) is None


if __name__ == "__main__":
    test_on_addon_delete_unsuspends_all_non_ignored_new_cards_before_deletion()
