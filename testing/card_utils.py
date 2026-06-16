"""
Utilities for manipulating and asserting Anki Card objects in a test collection.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from anki.consts import CARD_TYPE_REV, QUEUE_TYPE_REV

if TYPE_CHECKING:
    from anki.cards import Card, CardId
    from anki.collection import Collection


def set_review_card_state(col: "Collection", card: "Card", *, ivl: int) -> None:
    """
    Force a card into the 'Review' state with a specific interval.

    This is used to simulate 'mature' or 'immature' siblings.
    """
    card.type = CARD_TYPE_REV
    card.queue = QUEUE_TYPE_REV
    card.ivl = ivl
    card.due = 1  # Arbitrary due date (tomorrow)
    col.update_card(card)


def _load_custom_data(card: "Card") -> dict[str, object]:
    raw_custom_data = getattr(card, "custom_data", "")
    if not raw_custom_data:
        return {}

    try:
        parsed = json.loads(raw_custom_data)
    except (TypeError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def set_card_custom_data(col: "Collection", card: "Card", custom_data: dict[str, object]) -> None:
    fresh_card = col.get_card(card.id)
    fresh_card.custom_data = json.dumps(custom_data, ensure_ascii=False) if custom_data else ""
    col.update_card(fresh_card)


def card_custom_data(col: "Collection", card: "Card") -> dict[str, object]:
    return _load_custom_data(col.get_card(card.id))


def set_addon_custom_data(col: "Collection", card: "Card") -> None:
    data = card_custom_data(col, card)
    data["sibpush"] = "suspended"
    set_card_custom_data(col, card, data)


def clear_addon_custom_data(col: "Collection", card: "Card") -> None:
    data = card_custom_data(col, card)
    if data.pop("sibpush", None) is None:
        return
    set_card_custom_data(col, card, data)


def card_is_addon_owned(col: "Collection", card: "Card") -> bool:
    return card_custom_data(col, card).get("sibpush") == "suspended"


def assert_card_is_addon_owned(col: "Collection", card: "Card") -> None:
    assert card_is_addon_owned(col, card), f"Card {card.id} should be marked as SibPush-owned"


def assert_card_is_not_addon_owned(col: "Collection", card: "Card") -> None:
    assert not card_is_addon_owned(col, card), f"Card {card.id} should not be marked as SibPush-owned"


def card_queue(col: "Collection", card_id: "CardId") -> int:
    """
    Fetch the current queue status of a card directly from the database.

    0 = New, 2 = Review, -1 = Suspended.
    """
    return col.get_card(card_id).queue


def assert_card_queues(
    col: "Collection", cards: Sequence["Card"], expected_queues: Sequence[int]
) -> None:
    """
    Assert that a list of cards matches a sequence of expected queue statuses.
    """
    actual_queues = [card_queue(col, card.id) for card in cards]
    assert actual_queues == expected_queues, f"Expected {expected_queues}, but got {actual_queues}"
