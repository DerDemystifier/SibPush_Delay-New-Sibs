from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

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


def _build_collection_state(col, model):
    """Set up shared card fixtures used across delete-scenario tests.

    Returns a dict of named card lists so each scenario can access them by role.
    """
    deck_a_id = col.decks.id("SibPush Delete Deck A")
    deck_b_id = col.decks.id("SibPush Delete Deck B")

    note_a, cards_a = add_note_with_siblings(col, model, deck_a_id, "Delete cleanup note A")
    note_b, cards_b = add_note_with_siblings(col, model, deck_b_id, "Delete cleanup note B")
    set_review_card_state(col, cards_a[0], ivl=10)
    set_review_card_state(col, cards_b[0], ivl=10)

    return {
        "deck_a_id": deck_a_id,
        "deck_b_id": deck_b_id,
        "cards_a": cards_a,
        "cards_b": cards_b,
    }


def test_on_addon_delete_unsuspends_all_non_ignored_new_cards_before_deletion() -> None:
    """Deleting SibPush should restore every suspended new card except ignored ones (legacy behaviour)."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        state = _build_collection_state(col, model)
        cards_a = state["cards_a"]
        cards_b = state["cards_b"]

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            patched_addon.process_all_notes(col)

            assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
            assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])

            manual_note, manual_cards = add_note_with_siblings(col, model, state["deck_a_id"], "Manually suspended note")
            col.sched.suspend_cards([manual_cards[1].id])

            ignored_note, ignored_cards = add_note_with_siblings(col, model, state["deck_b_id"], "Ignored suspended note")
            review_note, review_cards = add_note_with_siblings(col, model, state["deck_b_id"], "Manually suspended review note")
            set_review_card_state(col, review_cards[0], ivl=10)

            set_card_custom_data(
                col,
                ignored_cards[2],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            col.sched.suspend_cards([ignored_cards[2].id])

            print_collection_state(col, "Before addon deletion (cards are add-on suspended)")

            # No dialog should appear because we mock askUser — but since there IS one ignored card,
            # we simulate the user declining (return=False) to get legacy behaviour.
            with patch.object(hooks_module, "askUser", return_value=False):
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


def test_on_addon_delete_clears_ignored_markers_when_user_confirms() -> None:
    """Confirming the clear dialog removes the ignored marker from every card and unsuspends new ones."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        state = _build_collection_state(col, model)
        cards_a = state["cards_a"]
        cards_b = state["cards_b"]

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            patched_addon.process_all_notes(col)

            # ignored_new_card: a suspended new card with the ignored marker
            ignored_note, ignored_cards = add_note_with_siblings(col, model, state["deck_b_id"], "Ignored suspended note")
            set_card_custom_data(
                col,
                ignored_cards[2],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            col.sched.suspend_cards([ignored_cards[2].id])

            # ignored_review_card: a non-new card with the ignored marker, not suspended by the addon
            ignored_review_note, ignored_review_cards = add_note_with_siblings(
                col, model, state["deck_b_id"], "Ignored review card note"
            )
            set_review_card_state(col, ignored_review_cards[0], ivl=10)
            set_card_custom_data(
                col,
                ignored_review_cards[0],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            # Do NOT suspend ignored_review_cards[0] — it should remain QUEUE_TYPE_REV after the delete

            assert_card_is_ignored(col, ignored_cards[2])
            assert_card_is_ignored(col, ignored_review_cards[0])

            review_queue_before = col.get_card(ignored_review_cards[0].id).queue

            print_collection_state(col, "Before addon deletion")

            with patch.object(hooks_module, "askUser", return_value=True):
                hooks_module.on_addon_delete(SimpleNamespace(), [addon.__name__])

        print_collection_state(col, "After addon deletion with confirmed clear")

        # The previously-ignored suspended new card should now be unsuspended
        assert_card_queues(col, ignored_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, ignored_cards[2])

        # The non-new ignored card should have its marker cleared but queue/suspend state unchanged
        assert_card_is_not_ignored(col, ignored_review_cards[0])
        assert col.get_card(ignored_review_cards[0].id).queue == review_queue_before

        # Addon-managed (non-ignored) new cards should be unsuspended as normal
        assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, cards_a[1])
        assert_card_is_not_ignored(col, cards_a[2])
        assert_card_is_not_ignored(col, cards_b[1])
        assert_card_is_not_ignored(col, cards_b[2])


def test_on_addon_delete_leaves_ignored_markers_when_user_declines() -> None:
    """Declining the clear dialog leaves all ignored markers and suspend states exactly as before."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        state = _build_collection_state(col, model)
        cards_a = state["cards_a"]
        cards_b = state["cards_b"]

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            patched_addon.process_all_notes(col)

            ignored_note, ignored_cards = add_note_with_siblings(col, model, state["deck_b_id"], "Ignored suspended note")
            set_card_custom_data(
                col,
                ignored_cards[2],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )
            col.sched.suspend_cards([ignored_cards[2].id])

            ignored_review_note, ignored_review_cards = add_note_with_siblings(
                col, model, state["deck_b_id"], "Ignored review card note"
            )
            set_review_card_state(col, ignored_review_cards[0], ivl=10)
            set_card_custom_data(
                col,
                ignored_review_cards[0],
                {state_module.ADDON_CUSTOM_DATA_KEY: state_module.ADDON_CUSTOM_DATA_IGNORED_VALUE},
            )

            review_queue_before = col.get_card(ignored_review_cards[0].id).queue

            print_collection_state(col, "Before addon deletion")

            with patch.object(hooks_module, "askUser", return_value=False):
                hooks_module.on_addon_delete(SimpleNamespace(), [addon.__name__])

        print_collection_state(col, "After addon deletion with declined clear")

        # The ignored new card's marker must still be present and card remains suspended
        assert_card_is_ignored(col, ignored_cards[2])
        assert_card_queues(col, ignored_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED])

        # The ignored review card's marker and queue must be untouched
        assert_card_is_ignored(col, ignored_review_cards[0])
        assert col.get_card(ignored_review_cards[0].id).queue == review_queue_before

        # Non-ignored addon-managed cards should still be unsuspended (unsuspend_all_addon_cards always runs)
        assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])


def test_on_addon_delete_shows_no_dialog_when_no_ignored_cards() -> None:
    """When no cards carry the ignored marker, the confirmation dialog must never appear."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        state = _build_collection_state(col, model)
        cards_a = state["cards_a"]
        cards_b = state["cards_b"]

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")

            patched_addon.process_all_notes(col)

            print_collection_state(col, "Before addon deletion (no ignored cards)")

            with patch.object(hooks_module, "askUser") as mock_ask:
                hooks_module.on_addon_delete(SimpleNamespace(), [addon.__name__])
                mock_ask.assert_not_called()

        print_collection_state(col, "After addon deletion (no ignored cards)")

        # Normal unsuspend behaviour should still apply
        assert_card_queues(col, cards_a, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_queues(col, cards_b, [QUEUE_TYPE_REV, QUEUE_TYPE_NEW, QUEUE_TYPE_NEW])
        assert_card_is_not_ignored(col, cards_a[1])
        assert_card_is_not_ignored(col, cards_a[2])
        assert_card_is_not_ignored(col, cards_b[1])
        assert_card_is_not_ignored(col, cards_b[2])
