"""Card suspension and deck-ignoring helpers for the SibPush workflow."""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Any, cast

from anki.cards import Card, CardId
from anki.collection import Collection
from anki.consts import QUEUE_TYPE_SUSPENDED
from anki.notes import Note, NoteId
from aqt.qt import QTimer
from aqt.utils import tooltip

from ..state import SUSPENDED_BY_ADDON_TAG
from .query import get_deck_rule

DECK_UNSUSPEND_BATCH_SIZE = 1000
DECK_UNSUSPEND_BATCH_PAUSE_MS = 500
DECK_UNSUSPEND_TOOLTIP_PERIOD_MS = 1500


def _get_variable_chunk_size(batch_size: int) -> int:
    """Return a slightly randomized chunk size around the provided batch size."""

    jitter = max(1, round(batch_size * 0.1))
    lower_bound = max(1, batch_size - jitter)
    upper_bound = batch_size + jitter
    return random.randint(lower_bound, upper_bound)


def suspend_cards(col: Collection, cards_to_suspend: Sequence[Card], note_id: NoteId) -> None:
    """Suspend a group of cards and mark their note as managed by the add-on.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.
        cards_to_suspend (Sequence[anki.cards.Card]): The cards to suspend.
        note_id (int): The note id associated with the cards.

    Returns:
        None: The operation is performed for its side effects.
    """

    cards_to_suspend = [card for card in cards_to_suspend if card.queue != QUEUE_TYPE_SUSPENDED]
    if not cards_to_suspend:
        return

    note = cards_to_suspend[0].note()

    if not note.has_tag(SUSPENDED_BY_ADDON_TAG):
        # Add tag to mark the note as managed by the addon, if already added, it won't be duplicated.
        note.add_tag(SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

    col.sched.suspend_cards([card.id for card in cards_to_suspend])


def remove_suspension_tag_if_no_suspended_cards(
    col: Collection, note: Note, cards: Sequence[Card]
) -> bool:
    """Remove the add-on suspension tag when the provided cards have no suspended cards left.

    Args:
        col (anki.collection.Collection): The collection that owns the note.
        note (anki.notes.Note): The note to inspect and update.
        cards (Sequence[anki.cards.Card]): The cards to inspect for suspension.

    Returns:
        bool: True when the tag was removed, otherwise False.
    """

    # Only drop the add-on tag once every sibling has been checked and none of them remain
    # suspended; otherwise a later pass would lose track of cards that still need restoring.
    for card in cards:
        if card.queue == QUEUE_TYPE_SUSPENDED:
            return False

    if not note.has_tag(SUSPENDED_BY_ADDON_TAG):
        return False

    note.remove_tag(SUSPENDED_BY_ADDON_TAG)
    col.update_note(note)
    return True


def note_is_ignored_deck(card: Card) -> bool:
    """Return whether a card belongs to a deck marked as ignored.

    Args:
        card (anki.cards.Card): The card to inspect.

    Returns:
        bool: True when the card's deck is configured to be ignored.
    """

    rule = get_deck_rule(card)
    return bool(rule and rule.get("ignored"))


def unsuspend_all_addon_cards_in_deck(col: Collection, deck_id: str) -> None:
    """Unsuspend all add-on-managed cards in a specific deck.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.
        deck_id (str): The deck id to scan for suspended cards.

    Returns:
        None: The matching cards are unsuspended for their side effects.
    """

    card_ids_to_unsuspend: list[CardId] = []
    notes_to_prune: dict[int, Note] = {}

    for card_id in col.find_cards(f"did:{deck_id}"):
        card = col.get_card(card_id)
        if card.queue != QUEUE_TYPE_SUSPENDED:
            continue

        note = card.note()
        if note.has_tag(SUSPENDED_BY_ADDON_TAG):
            card_ids_to_unsuspend.append(card.id)
            notes_to_prune[note.id] = note

    if not card_ids_to_unsuspend:
        return

    total_count = len(card_ids_to_unsuspend)

    def _show_unsuspend_progress(processed_count: int) -> None:
        tooltip(
            f"SibPush has restored {processed_count:,}/{total_count:,} cards from the ignored deck",
            period=DECK_UNSUSPEND_TOOLTIP_PERIOD_MS,
        )

    def _finish_unsuspending() -> None:
        for note in notes_to_prune.values():
            # Re-check the whole sibling set after unsuspending because the tag should remain
            # until the last add-on-managed suspended card on the note is gone.
            remove_suspension_tag_if_no_suspended_cards(col, note, note.cards())

    if total_count <= DECK_UNSUSPEND_BATCH_SIZE:
        col.sched.unsuspend_cards(card_ids_to_unsuspend)
        _show_unsuspend_progress(total_count)
        _finish_unsuspending()
        return

    displayed_count = 0

    def _process_chunk(start_index: int = 0) -> None:
        nonlocal displayed_count
        chunk_size = _get_variable_chunk_size(DECK_UNSUSPEND_BATCH_SIZE)
        chunk = card_ids_to_unsuspend[start_index : start_index + chunk_size]
        if not chunk:
            _finish_unsuspending()
            return

        col.sched.unsuspend_cards(chunk)
        displayed_count = min(total_count, displayed_count + len(chunk))
        _show_unsuspend_progress(displayed_count)

        next_index = start_index + len(chunk)
        if next_index >= total_count:
            _finish_unsuspending()
            return

        cast(Any, QTimer).singleShot(
            DECK_UNSUSPEND_BATCH_PAUSE_MS,
            lambda next_start_index=next_index: _process_chunk(next_start_index),
        )

    _show_unsuspend_progress(0)
    cast(Any, QTimer).singleShot(0, _process_chunk)


def unsuspend_all_addon_cards(col: Collection) -> None:
    """Unsuspend all add-on-managed cards across every deck.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.

    Returns:
        None: The matching cards are restored immediately for their side effects.
    """

    card_ids_to_unsuspend: list[CardId] = []
    notes_to_prune: dict[int, Note] = {}

    for card_id in col.find_cards(f"tag:{SUSPENDED_BY_ADDON_TAG} is:suspended"):
        card = col.get_card(card_id)
        if card.queue != QUEUE_TYPE_SUSPENDED:
            continue

        note = card.note()
        card_ids_to_unsuspend.append(card.id)
        notes_to_prune[note.id] = note

    if not card_ids_to_unsuspend:
        return

    for start_index in range(0, len(card_ids_to_unsuspend), DECK_UNSUSPEND_BATCH_SIZE):
        col.sched.unsuspend_cards(
            card_ids_to_unsuspend[start_index : start_index + DECK_UNSUSPEND_BATCH_SIZE]
        )

    for note in notes_to_prune.values():
        note.remove_tag(SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)
