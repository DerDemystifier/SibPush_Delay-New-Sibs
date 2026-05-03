"""
Utilities for manipulating and asserting Anki Card objects in a test collection.
"""

from __future__ import annotations

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
