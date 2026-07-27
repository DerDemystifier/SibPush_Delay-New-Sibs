from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    assert_card_is_ignored,
    assert_card_is_not_ignored,
    assert_card_is_not_suspended_by_addon,
    assert_card_is_suspended_by_addon,
    card_custom_data,
    set_card_custom_data,
    set_card_ignored,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id


def test_sibpush_marks_only_cards_it_suspends() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "provenance")
        set_review_card_state(col, cards[0], ivl=10)
        col.sched.suspend_cards([cards[2].id])

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)

        assert_card_is_not_suspended_by_addon(col, cards[0])
        assert_card_is_suspended_by_addon(col, cards[1])
        assert_card_is_not_suspended_by_addon(col, cards[2])


def test_manual_unsuspend_retains_provenance_until_sibpush_restores_card() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "manual unsuspend")

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)
            col.sched.unsuspend_cards([cards[1].id])
            assert_card_is_suspended_by_addon(col, cards[1])
            addon.process_all_notes(col)

        assert_card_is_suspended_by_addon(col, cards[1])
        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_SUSPENDED


def test_ignore_marker_preserves_provenance_queue_and_unrelated_data() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "independent markers")

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)
            state = import_module(f"{addon.__name__}.sibpush.state")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            set_card_custom_data(col, cards[1], {"third": "party"})
            suspension.mark_card_suspended_by_addon(col, cards[1])
            before_queue = col.get_card(cards[1].id).queue
            suspension.set_card_ignored(col, cards[1])

            assert col.get_card(cards[1].id).queue == before_queue
            assert_card_is_ignored(col, cards[1])
            assert_card_is_suspended_by_addon(col, cards[1])
            assert card_custom_data(col, cards[1])["third"] == "party"
            assert state.SIBPUSH_IGNORED_KEY in card_custom_data(col, cards[1])

            suspension.clear_card_ignored(col, cards[1])
            assert_card_is_not_ignored(col, cards[1])
            assert_card_is_suspended_by_addon(col, cards[1])
            assert col.get_card(cards[1].id).queue == before_queue


def test_deck_cleanup_restores_owned_card_and_removes_only_suspension_marker() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "deck cleanup")
        set_review_card_state(col, cards[0], ivl=10)

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)
            state = import_module(f"{addon.__name__}.sibpush.state")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            ignored_rule = {
                "did": str(deck_id),
                "name": "deck cleanup",
                state.CONFIG_IGNORED_KEY: True,
                "interval": 30,
            }
            addon.custom_deck_rules_by_did[str(deck_id)] = ignored_rule
            set_card_custom_data(col, cards[1], {"third": 1, state.SIBPUSH_IGNORED_KEY: True})
            suspension.mark_card_suspended_by_addon(col, cards[1])
            suspension.clear_card_ignored(col, cards[1])
            with patch.object(suspension, "tooltip"):
                suspension.unsuspend_all_addon_cards_in_deck(col, str(deck_id))

        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_NEW
        assert_card_is_not_suspended_by_addon(col, cards[1])
        assert card_custom_data(col, cards[1]) == {"third": 1}
        assert col.get_card(cards[2].id).queue == QUEUE_TYPE_NEW
        assert_card_is_not_suspended_by_addon(col, cards[2])


def test_cleanup_preserves_card_with_both_markers_even_when_delete_confirms_clear() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, owned_cards = add_note_with_siblings(col, model, deck_id, "owned")
        _, both_cards = add_note_with_siblings(col, model, deck_id, "both markers")
        set_review_card_state(col, owned_cards[0], ivl=10)
        set_review_card_state(col, both_cards[0], ivl=10)

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)
            state = import_module(f"{addon.__name__}.sibpush.state")
            hooks = import_module(f"{addon.__name__}.sibpush.hooks")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            suspension.set_card_ignored(col, both_cards[1])
            assert_card_is_suspended_by_addon(col, both_cards[1])

            with patch.object(hooks, "askUser", return_value=True):
                hooks.on_addon_delete(SimpleNamespace(), [addon.__name__])

        assert col.get_card(owned_cards[1].id).queue == QUEUE_TYPE_NEW
        assert col.get_card(both_cards[1].id).queue == QUEUE_TYPE_SUSPENDED
        assert_card_is_not_ignored(col, both_cards[1])
        assert_card_is_suspended_by_addon(col, both_cards[1])
        assert state.SIBPUSH_SUSPENDED_KEY in card_custom_data(col, both_cards[1])


def test_legacy_ignore_migration_preserves_third_party_data_and_is_idempotent() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "legacy migration")
        with patched_addon_state(col) as addon:
            state = import_module(f"{addon.__name__}.sibpush.state")
            migration = import_module(f"{addon.__name__}.sibpush.migration")
            raw = {state.LEGACY_ADDON_CUSTOM_DATA_KEY: state.LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE, "third": {"x": 1}}
            set_card_custom_data(col, cards[1], raw)
            migration.migrate_legacy_ignore_markers(col)
            migrated = card_custom_data(col, cards[1])
            assert migrated == {state.SIBPUSH_IGNORED_KEY: True, "third": {"x": 1}}
            migration.migrate_legacy_ignore_markers(col)
            assert card_custom_data(col, cards[1]) == migrated

            malformed_card = SimpleNamespace(id=cards[2].id, custom_data="not-json")
            malformed_collection = SimpleNamespace(
                find_cards=lambda _query: [malformed_card.id],
                get_card=lambda _card_id: malformed_card,
            )
            migration.migrate_legacy_ignore_markers(malformed_collection)
            assert malformed_card.custom_data == "not-json"


def test_one_ignored_sibling_does_not_hide_other_eligible_siblings() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "partial ignore")
        set_card_ignored(col, cards[1])

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)

        assert_card_is_ignored(col, cards[1])
        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_NEW
        assert col.get_card(cards[2].id).queue == QUEUE_TYPE_SUSPENDED
        assert_card_is_suspended_by_addon(col, cards[2])


def test_target_build_custom_data_search_syntax_is_positive_only() -> None:
    """Positive marker searches work; Python remains authoritative for exclusions."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "search syntax")

        with patched_addon_state(col) as addon:
            state = import_module(f"{addon.__name__}.sibpush.state")
            set_card_ignored(col, cards[1])
            positive = f"prop:cds:{state.SIBPUSH_IGNORED_KEY}=true"
            presence = f"has-cd:{state.SIBPUSH_IGNORED_KEY}"
            negative = f"prop:cds:{state.SIBPUSH_IGNORED_KEY}!=true"

            assert cards[1].id in col.find_cards(positive)
            assert cards[1].id in col.find_cards(presence)
            # This Anki build does not return cards without the key for `!=`; cleanup therefore
            # uses positive candidates and performs ignored-marker exclusion in Python.
            assert list(col.find_cards(negative)) == []


def test_scheduler_failure_does_not_infer_suspension_provenance() -> None:
    """A failed/partial suspend batch leaves provenance unchanged."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        note, cards = add_note_with_siblings(col, model, deck_id, "failed suspend")

        with patched_addon_state(col) as addon:
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            original_suspend = col.sched.suspend_cards

            def partially_suspend_then_fail(card_ids):
                original_suspend(card_ids[:1])
                raise RuntimeError("simulated scheduler failure")

            with patch.object(col.sched, "suspend_cards", side_effect=partially_suspend_then_fail):
                try:
                    suspension.suspend_cards(col, cards[1:], note.id)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("expected the scheduler failure")

        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_SUSPENDED
        assert_card_is_not_suspended_by_addon(col, cards[1])
        assert col.get_card(cards[2].id).queue == QUEUE_TYPE_NEW
        assert_card_is_not_suspended_by_addon(col, cards[2])


def test_scheduler_failure_preserves_restoration_provenance_after_partial_success() -> None:
    """A failed/partial unsuspend batch preserves every existing provenance marker."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "failed restore")

        with patched_addon_state(col) as addon:
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            for card in cards[1:]:
                col.sched.suspend_cards([card.id])
                suspension.mark_card_suspended_by_addon(col, card)
            suspended_cards = [col.get_card(card.id) for card in cards[1:]]

            original_unsuspend = col.sched.unsuspend_cards

            def partially_unsuspend_then_fail(card_ids):
                original_unsuspend(card_ids[:1])
                raise RuntimeError("simulated scheduler failure")

            with patch.object(
                col.sched, "unsuspend_cards", side_effect=partially_unsuspend_then_fail
            ):
                try:
                    suspension.unsuspend_cards(col, suspended_cards)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("expected the scheduler failure")

        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_NEW
        assert_card_is_suspended_by_addon(col, cards[1])
        assert col.get_card(cards[2].id).queue == QUEUE_TYPE_SUSPENDED
        assert_card_is_suspended_by_addon(col, cards[2])


def test_direct_legacy_ignore_clear_preserves_new_marker_and_third_party_data() -> None:
    """Direct cleanup removes both ignored formats without touching other metadata."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "legacy clear")

        with patched_addon_state(col) as addon:
            state = import_module(f"{addon.__name__}.sibpush.state")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            set_card_custom_data(
                col,
                cards[1],
                {
                    state.LEGACY_ADDON_CUSTOM_DATA_KEY: state.LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE,
                    state.SIBPUSH_IGNORED_KEY: True,
                    state.SIBPUSH_SUSPENDED_KEY: True,
                    "third": {"keep": True},
                },
            )

            suspension.clear_card_ignored(col, cards[1])

            malformed_card = SimpleNamespace(id=cards[2].id, custom_data="not-json")
            malformed_collection = SimpleNamespace(
                get_card=lambda _card_id: malformed_card,
                update_card=lambda _card: (_ for _ in ()).throw(
                    AssertionError("malformed custom data must not be written")
                ),
            )
            suspension.clear_card_ignored(malformed_collection, malformed_card)

        data = card_custom_data(col, cards[1])
        assert state.LEGACY_ADDON_CUSTOM_DATA_KEY not in data
        assert state.SIBPUSH_IGNORED_KEY not in data
        assert data[state.SIBPUSH_SUSPENDED_KEY] is True
        assert data["third"] == {"keep": True}
        assert malformed_card.custom_data == "not-json"


def test_normal_promotion_removes_suspension_provenance() -> None:
    """Normal SibPush promotion clears provenance after its own unsuspend succeeds."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        note, cards = add_note_with_siblings(col, model, deck_id, "normal promotion")

        with patched_addon_state(col) as addon:
            addon.process_all_notes(col)
            set_review_card_state(col, cards[0], ivl=30)
            addon.process_note(col, note.id)

        assert col.get_card(cards[1].id).queue == QUEUE_TYPE_NEW
        assert_card_is_not_suspended_by_addon(col, cards[1])


def test_async_deck_cleanup_stops_when_deck_is_unignored_between_chunks() -> None:
    """A queued callback must not restore cards after the deck becomes active again."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards_a = add_note_with_siblings(col, model, deck_id, "async unignore A")
        _, cards_b = add_note_with_siblings(col, model, deck_id, "async unignore B")
        set_review_card_state(col, cards_a[0], ivl=10)
        set_review_card_state(col, cards_b[0], ivl=10)

        with patched_addon_state(col) as addon:
            state = import_module(f"{addon.__name__}.sibpush.state")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            addon.process_all_notes(col)
            ignored_rule = {
                "did": str(deck_id),
                "name": "async unignore",
                state.CONFIG_IGNORED_KEY: True,
                "interval": 30,
            }
            addon.custom_deck_rules_by_did[str(deck_id)] = ignored_rule
            suspension.DECK_UNSUSPEND_BATCH_SIZE = 1

            def fake_single_shot(delay, callback):
                if delay == suspension.DECK_UNSUSPEND_BATCH_PAUSE_MS:
                    ignored_rule[state.CONFIG_IGNORED_KEY] = False
                callback()

            with patch.object(suspension, "tooltip"), patch.object(
                suspension.QTimer, "singleShot", side_effect=fake_single_shot
            ):
                suspension.unsuspend_all_addon_cards_in_deck(col, str(deck_id))

        suspended_cards = [cards_a[1], cards_a[2], cards_b[1], cards_b[2]]
        assert any(
            col.get_card(card.id).queue == QUEUE_TYPE_SUSPENDED for card in suspended_cards
        )
        assert any(
            card_custom_data(col, card).get(state.SIBPUSH_SUSPENDED_KEY) is True
            for card in suspended_cards
        )


def test_async_deck_cleanup_skips_cards_moved_before_their_chunk() -> None:
    """A card moved out of the requested deck is not restored by a stale batch."""

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        other_deck_id = col.decks.id("SibPush moved card destination")
        _, cards_a = add_note_with_siblings(col, model, deck_id, "async move A")
        _, cards_b = add_note_with_siblings(col, model, deck_id, "async move B")
        set_review_card_state(col, cards_a[0], ivl=10)
        set_review_card_state(col, cards_b[0], ivl=10)

        with patched_addon_state(col) as addon:
            state = import_module(f"{addon.__name__}.sibpush.state")
            suspension = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            addon.process_all_notes(col)
            addon.custom_deck_rules_by_did[str(deck_id)] = {
                "did": str(deck_id),
                "name": "async move",
                state.CONFIG_IGNORED_KEY: True,
                "interval": 30,
            }
            suspension.DECK_UNSUSPEND_BATCH_SIZE = 1
            moved = False

            def fake_single_shot(delay, callback):
                nonlocal moved
                if delay == suspension.DECK_UNSUSPEND_BATCH_PAUSE_MS and not moved:
                    moved = True
                    for card in cards_a[1:] + cards_b[1:]:
                        fresh_card = col.get_card(card.id)
                        fresh_card.did = other_deck_id
                        col.update_card(fresh_card)
                callback()

            with patch.object(suspension, "tooltip"), patch.object(
                suspension.QTimer, "singleShot", side_effect=fake_single_shot
            ):
                suspension.unsuspend_all_addon_cards_in_deck(col, str(deck_id))

        assert any(
            col.get_card(card.id).queue == QUEUE_TYPE_SUSPENDED for card in cards_a[1:] + cards_b[1:]
        )


if __name__ == "__main__":
    test_sibpush_marks_only_cards_it_suspends()
    test_manual_unsuspend_retains_provenance_until_sibpush_restores_card()
    test_ignore_marker_preserves_provenance_queue_and_unrelated_data()
    test_deck_cleanup_restores_owned_card_and_removes_only_suspension_marker()
    test_cleanup_preserves_card_with_both_markers_even_when_delete_confirms_clear()
    test_legacy_ignore_migration_preserves_third_party_data_and_is_idempotent()
    test_one_ignored_sibling_does_not_hide_other_eligible_siblings()
    test_target_build_custom_data_search_syntax_is_positive_only()
    test_scheduler_failure_does_not_infer_suspension_provenance()
    test_scheduler_failure_preserves_restoration_provenance_after_partial_success()
    test_direct_legacy_ignore_clear_preserves_new_marker_and_third_party_data()
    test_normal_promotion_removes_suspension_provenance()
    test_async_deck_cleanup_stops_when_deck_is_unignored_between_chunks()
    test_async_deck_cleanup_skips_cards_moved_before_their_chunk()
