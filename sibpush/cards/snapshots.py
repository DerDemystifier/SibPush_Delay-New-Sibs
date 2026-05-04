"""Card snapshot helpers used for debug logging."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from anki.cards import Card


@dataclass(frozen=True)
class CardSnapshot:
    """Immutable record of a card's state for logging comparisons."""

    id: int
    queue: int
    type: int
    ivl: int
    due: int
    did: int
    flags: int


def capture_snapshots(cards: Sequence[Card]) -> list[CardSnapshot]:
    """Capture the current state of a sequence of cards.

    Args:
        cards (Sequence[anki.cards.Card]): The cards to snapshot.

    Returns:
        list[CardSnapshot]: The captured card state records in input order.
    """

    return [
        CardSnapshot(
            id=card.id,
            queue=card.queue,
            type=card.type,
            ivl=card.ivl,
            due=card.due,
            did=card.did,
            flags=card.flags,
        )
        for card in cards
    ]
