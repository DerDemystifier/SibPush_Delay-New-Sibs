"""Undo scenarios for SibPush batch processing and card cleanup actions."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from typing import TYPE_CHECKING

from anki.collection import Collection
from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_REV, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import (
    set_card_ignored,
    set_card_suspended_by_addon,
    set_review_card_state,
)
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id

if TYPE_CHECKING:
    from anki.cards import Card


def _snapshot_cards(
    col: Collection, cards: Sequence[Card]
) -> tuple[tuple[int, str], ...]:
    return tuple(
        (fresh_card.queue, fresh_card.custom_data)
        for card in cards
        for fresh_card in (col.get_card(card.id),)
    )


def test_note_batch_merges_changes_into_current_undo_entry() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        first_note, first_cards = add_note_with_siblings(
            col, model, deck_id, "First batch note"
        )
        second_note, second_cards = add_note_with_siblings(
            col, model, deck_id, "Second batch note"
        )
        cards = [*first_cards, *second_cards]
        before_batch = _snapshot_cards(col, cards)
        col.add_custom_undo_entry("Prior action")

        with patched_addon_state(col) as addon:
            notes_module = import_module(f"{addon.__name__}.sibpush.processing.notes")
            notes_module._process_note_batch(col, [first_note.id, second_note.id])

            undo_label = col.undo_status().undo
            assert undo_label == "Prior action", undo_label
            after_batch = _snapshot_cards(col, cards)
            assert [queue for queue, _ in after_batch] == [
                QUEUE_TYPE_NEW,
                QUEUE_TYPE_SUSPENDED,
                QUEUE_TYPE_SUSPENDED,
                QUEUE_TYPE_NEW,
                QUEUE_TYPE_SUSPENDED,
                QUEUE_TYPE_SUSPENDED,
            ]

            col.undo()
            assert _snapshot_cards(col, cards) == before_batch
            assert col.undo_status().redo == "Prior action"

            col.redo()
            assert _snapshot_cards(col, cards) == after_batch
            assert col.undo_status().undo == "Prior action"


def test_noop_note_batch_does_not_create_an_undo_entry() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=1)
        deck_id = make_test_deck_id(col)
        note, _ = add_note_with_siblings(
            col,
            model,
            deck_id,
            "Single-card batch note",
            expected_card_count=1,
        )

        with patched_addon_state(col) as addon:
            notes_module = import_module(f"{addon.__name__}.sibpush.processing.notes")
            before_status = col.undo_status()
            notes_module._process_note_batch(col, [note.id])
            after_status = col.undo_status()
            assert after_status.last_step == before_status.last_step
            assert after_status.undo == before_status.undo


def test_note_batch_scan_merges_into_answer_card_on_real_collection() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=4)
        note, cards = add_note_with_siblings(
            col,
            model,
            make_test_deck_id(col),
            "Batch scan after answer",
            expected_card_count=4,
        )
        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])

        with patched_addon_state(col) as addon:
            set_card_suspended_by_addon(col, col.get_card(cards[1].id))
            before_answer = _snapshot_cards(col, cards)

            answered_card = col.get_card(cards[0].id)
            answered_card.start_timer()
            col.sched.answerCard(answered_card, 3)
            undo_label = col.undo_status().undo
            assert undo_label == "Answer Card", undo_label

            notes_module = import_module(f"{addon.__name__}.sibpush.processing.notes")
            notes_module._process_note_batch(col, [note.id])

            undo_label = col.undo_status().undo
            assert undo_label == "Answer Card", undo_label
            after_scan = _snapshot_cards(col, cards)
            assert [queue for queue, _ in after_scan] == [
                QUEUE_TYPE_REV,
                QUEUE_TYPE_NEW,
                QUEUE_TYPE_SUSPENDED,
                QUEUE_TYPE_SUSPENDED,
            ]
            assert after_scan != before_answer

            col.undo()
            assert _snapshot_cards(col, cards) == before_answer
            assert col.undo_status().redo == "Answer Card"

            col.redo()
            assert _snapshot_cards(col, cards) == after_scan


def test_restore_chunk_groups_unsuspend_and_marker_changes() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(col, model, deck_id, "Restore chunk")
        col.sched.suspend_cards([cards[1].id, cards[2].id])

        with patched_addon_state(col) as addon:
            suspension_module = import_module(
                f"{addon.__name__}.sibpush.processing.suspension"
            )
            for card in cards[1:]:
                set_card_suspended_by_addon(col, card)
            before_restore = _snapshot_cards(col, cards)

            restored_count = suspension_module._restore_chunk(
                col, [card.id for card in cards[1:]]
            )

            assert restored_count == 2
            assert col.undo_status().undo == "Restore SibPush cards"
            after_restore = _snapshot_cards(col, cards)
            assert [queue for queue, _ in after_restore] == [
                QUEUE_TYPE_NEW,
                QUEUE_TYPE_NEW,
                QUEUE_TYPE_NEW,
            ]

            col.undo()
            assert _snapshot_cards(col, cards) == before_restore

            col.redo()
            assert _snapshot_cards(col, cards) == after_restore


def test_clear_ignored_marker_chunk_groups_card_updates() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=2)
        deck_id = make_test_deck_id(col)
        _, cards = add_note_with_siblings(
            col, model, deck_id, "Ignored marker cleanup", expected_card_count=2
        )

        with patched_addon_state(col) as addon:
            set_card_ignored(col, cards[0])
            set_card_ignored(col, cards[1])
            suspension_module = import_module(
                f"{addon.__name__}.sibpush.processing.suspension"
            )
            before_clear = _snapshot_cards(col, cards)

            suspension_module.clear_all_addon_ignored_markers(col)

            assert col.undo_status().undo == "Clear SibPush ignored markers"
            after_clear = _snapshot_cards(col, cards)
            assert all(not custom_data for _, custom_data in after_clear)

            col.undo()
            assert _snapshot_cards(col, cards) == before_clear

            col.redo()
            assert _snapshot_cards(col, cards) == after_clear
