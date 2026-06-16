"""Card suspension and deck-ignoring helpers for the SibPush workflow."""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from typing import Any, cast

from anki.cards import Card, CardId
from anki.collection import Collection
from anki.consts import QUEUE_TYPE_SUSPENDED
from anki.notes import NoteId
from aqt.qt import QTimer
from aqt.utils import tooltip

from ..state import ADDON_CUSTOM_DATA_KEY, ADDON_CUSTOM_DATA_VALUE
from .query import get_deck_rule

DECK_UNSUSPEND_BATCH_SIZE = 1000
DECK_UNSUSPEND_BATCH_PAUSE_MS = 100
DECK_UNSUSPEND_TOOLTIP_PERIOD_MS = 3000


def _get_variable_chunk_size(batch_size: int) -> int:
    """Return a slightly randomized chunk size around the provided batch size."""

    jitter = max(1, round(batch_size * 0.1))
    lower_bound = max(1, batch_size - jitter)
    upper_bound = batch_size + jitter
    return random.randint(lower_bound, upper_bound)


def _load_custom_data(card: Card) -> dict[str, Any]:
    """Return a parsed copy of a card's custom_data payload."""

    raw_custom_data = getattr(card, "custom_data", "")
    if not raw_custom_data:
        return {}

    try:
        parsed_custom_data = json.loads(raw_custom_data)
    except (TypeError, json.JSONDecodeError):
        return {}

    if isinstance(parsed_custom_data, dict):
        return cast(dict[str, Any], parsed_custom_data)

    return {}


def _write_custom_data(col: Collection, card: Card, custom_data: dict[str, Any]) -> None:
    """Persist custom_data back to a card without clobbering the rest of the blob."""

    fresh_card = col.get_card(card.id)
    fresh_card.custom_data = json.dumps(custom_data, ensure_ascii=False) if custom_data else ""
    col.update_card(fresh_card)


def _set_addon_custom_data(col: Collection, card: Card) -> bool:
    """Mark a card as SibPush-owned while preserving other custom_data keys."""

    fresh_card = col.get_card(card.id)
    custom_data = _load_custom_data(fresh_card)
    if custom_data.get(ADDON_CUSTOM_DATA_KEY) == ADDON_CUSTOM_DATA_VALUE:
        return False

    custom_data[ADDON_CUSTOM_DATA_KEY] = ADDON_CUSTOM_DATA_VALUE
    _write_custom_data(col, fresh_card, custom_data)
    return True


def _clear_addon_custom_data(col: Collection, card: Card) -> bool:
    """Remove SibPush ownership from a card while preserving other custom_data keys."""

    fresh_card = col.get_card(card.id)
    custom_data = _load_custom_data(fresh_card)
    if ADDON_CUSTOM_DATA_KEY not in custom_data:
        return False

    custom_data.pop(ADDON_CUSTOM_DATA_KEY, None)
    _write_custom_data(col, fresh_card, custom_data)
    return True


def card_is_addon_owned(card: Card) -> bool:
    """Return whether a card is marked as SibPush-owned."""

    return _load_custom_data(card).get(ADDON_CUSTOM_DATA_KEY) == ADDON_CUSTOM_DATA_VALUE


def suspend_cards(col: Collection, cards_to_suspend: Sequence[Card], note_id: NoteId) -> None:
    """Suspend a group of cards and mark each card as managed by the add-on.

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

    col.sched.suspend_cards([card.id for card in cards_to_suspend])

    for card in cards_to_suspend:
        _set_addon_custom_data(col, card)


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

    for card_id in col.find_cards(f"did:{deck_id} has-cd:{ADDON_CUSTOM_DATA_KEY} is:suspended"):
        card = col.get_card(card_id)
        if card.queue == QUEUE_TYPE_SUSPENDED:
            card_ids_to_unsuspend.append(card.id)

    if not card_ids_to_unsuspend:
        return

    total_count = len(card_ids_to_unsuspend)

    def _show_unsuspend_progress(processed_count: int) -> None:
        tooltip(
            f"SibPush has restored {processed_count:,}/{total_count:,} cards from the ignored deck",
            period=DECK_UNSUSPEND_TOOLTIP_PERIOD_MS,
        )

    def _finish_unsuspending() -> None:
        for card_id in card_ids_to_unsuspend:
            _clear_addon_custom_data(col, col.get_card(card_id))

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

    for card_id in col.find_cards(f"has-cd:{ADDON_CUSTOM_DATA_KEY} is:suspended"):
        card = col.get_card(card_id)
        if card.queue != QUEUE_TYPE_SUSPENDED:
            continue

        card_ids_to_unsuspend.append(card.id)

    if not card_ids_to_unsuspend:
        return

    for start_index in range(0, len(card_ids_to_unsuspend), DECK_UNSUSPEND_BATCH_SIZE):
        chunk = card_ids_to_unsuspend[start_index : start_index + DECK_UNSUSPEND_BATCH_SIZE]
        col.sched.unsuspend_cards(chunk)
        for card_id in chunk:
            _clear_addon_custom_data(col, col.get_card(card_id))
