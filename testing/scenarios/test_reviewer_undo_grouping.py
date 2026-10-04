"""Scenarios for merging reviewer-triggered SibPush changes into Answer Card undo."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

from anki.collection import Collection
from anki.consts import QUEUE_TYPE_REV, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED

from ..addon_utils import load_addon_module, patched_addon_state
from ..card_utils import set_card_suspended_by_addon, set_review_card_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id

if TYPE_CHECKING:
    from anki.cards import Card


@dataclass
class FakeUndoStatus:
    last_step: int


class FakeUndoCollection:
    def __init__(
        self,
        last_step: int,
        merge_error: Exception | None = None,
        status_error: Exception | None = None,
    ) -> None:
        self.last_step = last_step
        self.merge_error = merge_error
        self.status_error = status_error
        self.undo_status_calls = 0
        self.merge_targets: list[int] = []

    def undo_status(self) -> FakeUndoStatus:
        self.undo_status_calls += 1
        if self.status_error is not None:
            raise self.status_error
        return FakeUndoStatus(last_step=self.last_step)

    def merge_undo_entries(self, target: int) -> None:
        self.merge_targets.append(target)
        if self.merge_error is not None:
            raise self.merge_error


def _load_reviewer_modules() -> tuple[ModuleType, ModuleType]:
    load_addon_module()
    module_root = "sibpush_test_addon.sibpush"
    hooks_module = importlib.import_module(f"{module_root}.hooks")
    undo_module = importlib.import_module(f"{module_root}.processing.undo")
    return hooks_module, undo_module


def _call_reviewer_hook(hooks_module: ModuleType, col: FakeUndoCollection) -> None:
    reviewer = SimpleNamespace(mw=SimpleNamespace(col=col))
    card = SimpleNamespace(nid=123)
    getattr(hooks_module, "reviewer_did_answer_card")(reviewer, card, 3)


def test_reviewer_hook_merges_new_undo_entries_once() -> None:
    col = FakeUndoCollection(last_step=41)
    hooks_module, _ = _load_reviewer_modules()

    def process_note(
        processed_col: FakeUndoCollection, note_id: int, *, coming_from_reviewer_hook: bool
    ) -> None:
        assert processed_col is col
        assert note_id == 123
        assert coming_from_reviewer_hook
        col.last_step = 44

    with patch.object(hooks_module, "process_note", side_effect=process_note) as process:
        _call_reviewer_hook(hooks_module, col)

    process.assert_called_once_with(col, 123, coming_from_reviewer_hook=True)
    assert col.merge_targets == [41]
    assert col.undo_status_calls == 2


def test_reviewer_hook_does_not_merge_when_undo_state_is_unchanged() -> None:
    col = FakeUndoCollection(last_step=41)
    hooks_module, _ = _load_reviewer_modules()

    with patch.object(hooks_module, "process_note") as process:
        _call_reviewer_hook(hooks_module, col)

    process.assert_called_once_with(col, 123, coming_from_reviewer_hook=True)
    assert col.merge_targets == []
    assert col.undo_status_calls == 2


def test_reviewer_hook_does_not_merge_without_a_prior_undo_entry() -> None:
    col = FakeUndoCollection(last_step=0)
    hooks_module, _ = _load_reviewer_modules()

    def process_note(
        processed_col: FakeUndoCollection, note_id: int, *, coming_from_reviewer_hook: bool
    ) -> None:
        assert processed_col is col
        assert note_id == 123
        assert coming_from_reviewer_hook
        col.last_step = 1

    with patch.object(hooks_module, "process_note", side_effect=process_note):
        _call_reviewer_hook(hooks_module, col)

    assert col.merge_targets == []
    assert col.undo_status_calls == 2


def test_reviewer_hook_continues_when_initial_undo_status_read_fails() -> None:
    col = FakeUndoCollection(
        last_step=41, status_error=RuntimeError("undo status unavailable")
    )
    hooks_module, undo_module = _load_reviewer_modules()

    with patch.object(undo_module, "logThis") as log_this:
        with patch.object(hooks_module, "process_note") as process:
            _call_reviewer_hook(hooks_module, col)

    process.assert_called_once_with(col, 123, coming_from_reviewer_hook=True)
    assert col.undo_status_calls == 1
    assert col.merge_targets == []
    log_this.assert_called_once()
    log_message = log_this.call_args.args[0]
    assert "read the current undo step" in cast(Callable[[], str], log_message)()


def test_reviewer_hook_logs_merge_failure_without_breaking_review() -> None:
    col = FakeUndoCollection(last_step=41, merge_error=RuntimeError("merge failed"))
    hooks_module, undo_module = _load_reviewer_modules()

    def process_note(
        processed_col: FakeUndoCollection, note_id: int, *, coming_from_reviewer_hook: bool
    ) -> None:
        assert processed_col is col
        assert note_id == 123
        assert coming_from_reviewer_hook
        col.last_step = 44

    with patch.object(undo_module, "logThis") as log_this:
        with patch.object(hooks_module, "process_note", side_effect=process_note) as process:
            _call_reviewer_hook(hooks_module, col)

    process.assert_called_once_with(col, 123, coming_from_reviewer_hook=True)
    assert col.merge_targets == [41]
    log_this.assert_called_once()
    log_message = log_this.call_args.args[0]
    assert callable(log_message)
    assert "merge failed" in cast(Callable[[], str], log_message)()


def test_reviewer_hook_preserves_processing_error_when_merge_fails() -> None:
    processing_error = ValueError("processing failed")
    col = FakeUndoCollection(last_step=41, merge_error=RuntimeError("merge failed"))
    hooks_module, undo_module = _load_reviewer_modules()

    def process_note(
        processed_col: FakeUndoCollection, note_id: int, *, coming_from_reviewer_hook: bool
    ) -> None:
        assert processed_col is col
        assert note_id == 123
        assert coming_from_reviewer_hook
        col.last_step = 44
        raise processing_error

    with patch.object(undo_module, "logThis") as log_this:
        with patch.object(hooks_module, "process_note", side_effect=process_note):
            try:
                _call_reviewer_hook(hooks_module, col)
            except ValueError as error:
                assert error is processing_error
            else:
                raise AssertionError("process_note exception was not propagated")

    assert col.merge_targets == [41]
    log_this.assert_called_once()


def _snapshot_cards(
    col: Collection, cards: Sequence[Card]
) -> dict[int, tuple[int, int, int, int, int, int, str]]:
    snapshots: dict[int, tuple[int, int, int, int, int, int, str]] = {}
    for card in cards:
        current = col.get_card(card.id)
        snapshots[int(current.id)] = (
            current.type,
            current.queue,
            current.due,
            current.ivl,
            current.reps,
            current.lapses,
            current.custom_data,
        )
    return snapshots


def test_single_undo_restores_answer_and_reviewer_sibpush_changes() -> None:
    with temporary_collection() as col:
        model = build_test_notetype(col, card_count=4)
        _, cards = add_note_with_siblings(
            col,
            model,
            make_test_deck_id(col),
            "Undo grouping",
            expected_card_count=4,
        )
        set_review_card_state(col, cards[0], ivl=60)
        col.sched.suspend_cards([cards[1].id])

        with patched_addon_state(col):
            set_card_suspended_by_addon(col, col.get_card(cards[1].id))
            before_answer = _snapshot_cards(col, cards)

            answered_card = col.get_card(cards[0].id)
            answered_card.start_timer()
            col.sched.answerCard(answered_card, 3)
            assert col.undo_status().undo == "Answer Card"

            hooks_module = importlib.import_module("sibpush_test_addon.sibpush.hooks")
            reviewer = SimpleNamespace(mw=SimpleNamespace(col=col))
            getattr(hooks_module, "reviewer_did_answer_card")(reviewer, answered_card, 3)

            assert col.undo_status().undo == "Answer Card"
            after_reviewer = _snapshot_cards(col, cards)
            assert [state[1] for state in after_reviewer.values()] == [
                QUEUE_TYPE_REV,
                QUEUE_TYPE_SIBLING_BURIED,
                QUEUE_TYPE_SUSPENDED,
                QUEUE_TYPE_SUSPENDED,
            ]

            col.undo()
            assert _snapshot_cards(col, cards) == before_answer
            assert col.undo_status().redo == "Answer Card"

            col.redo()
            assert _snapshot_cards(col, cards) == after_reviewer
            assert col.undo_status().undo == "Answer Card"
