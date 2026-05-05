"""Helpers for classifying sibling cards by state."""

from __future__ import annotations

from collections.abc import Sequence

from anki.cards import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED, Card


def classify_cards(
    siblings: Sequence[Card], interval_threshold: int
) -> tuple[list[Card], list[Card]]:
    """Split sibling cards into new and immature groups.
    Immature cards are those that have a review interval below the given threshold, meaning they have been reviewed at least once but haven't reached a certain level of maturity yet.
    New cards are those that haven't been reviewed at all.

    Args:
        siblings (Sequence[anki.cards.Card]): The sibling cards to classify.
        interval_threshold (int): The minimum review interval that counts as mature.

    Returns:
        tuple[list[anki.cards.Card], list[anki.cards.Card]]: A tuple containing the new cards
            first and the immature cards second.
    """

    new_cards: list[Card] = []
    immature_cards: list[Card] = []
    for sibling in siblings:
        if sibling.queue == QUEUE_TYPE_SUSPENDED:
            # This means the card is suspended, so we don't care about it.
            continue

        if sibling.type == CARD_TYPE_NEW:
            new_cards.append(sibling)
        elif sibling.ivl < interval_threshold:
            immature_cards.append(sibling)

    return new_cards, immature_cards
