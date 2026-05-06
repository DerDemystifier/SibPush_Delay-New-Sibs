"""Helpers for classifying sibling cards by state."""

from __future__ import annotations

from collections.abc import Sequence

from anki.cards import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED, Card


def classify_cards(
    siblings: Sequence[Card], interval_threshold: int
) -> tuple[list[Card], list[Card]]:
    """Split sibling cards into new and immature groups.

    This is the core classification logic that determines which cards need to be suspended.

    Immature cards are those that have been reviewed at least once but haven't reached
    the configured maturity threshold (default 21 days). These cards block the introduction
    of their new siblings because they're still being learned.

    New cards are those that haven't been reviewed at all yet.

    Suspended cards are ignored entirely since they're already out of the review rotation.

    Args:
        siblings (Sequence[anki.cards.Card]): The sibling cards to classify.
        interval_threshold (int): The minimum review interval (in days) that counts as mature.
            Cards with intervals below this are considered immature.

    Returns:
        tuple[list[anki.cards.Card], list[anki.cards.Card]]: A tuple containing:
            - new_cards: Cards that haven't been reviewed yet (type == CARD_TYPE_NEW)
            - immature_cards: Cards with interval < threshold (still being learned)
    """

    new_cards: list[Card] = []
    immature_cards: list[Card] = []

    for sibling in siblings:
        # Skip suspended cards - they're already out of rotation and don't affect scheduling
        if sibling.queue == QUEUE_TYPE_SUSPENDED:
            continue

        # Classify based on card state
        if sibling.type == CARD_TYPE_NEW:
            # Never reviewed - this is a candidate for suspension
            new_cards.append(sibling)
        elif sibling.ivl < interval_threshold:
            # Reviewed but not mature - blocks introduction of new siblings
            immature_cards.append(sibling)
        # Cards with ivl >= interval_threshold are mature and don't block anything

    return new_cards, immature_cards
