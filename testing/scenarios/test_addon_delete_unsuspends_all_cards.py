from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import assert_card_queues, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype
from ..print_utils import print_collection_state


def test_on_addon_delete_unsuspends_all_addon_cards_before_deletion() -> None:
    """Deleting SibPush should immediately restore every card it suspended."""

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
            assert col.get_note(note_a.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
            assert col.get_note(note_b.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)

            print_collection_state(col, "Before addon deletion (cards are add-on suspended)")

            hooks_module.on_addon_delete(SimpleNamespace(), [addon.__name__])

        print_collection_state(col, "After addon deletion (cards restored immediately)")

        assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert not col.get_note(note_a.id).has_tag("SibPush-suspended")
        assert not col.get_note(note_b.id).has_tag("SibPush-suspended")


if __name__ == "__main__":
    test_on_addon_delete_unsuspends_all_addon_cards_before_deletion()
