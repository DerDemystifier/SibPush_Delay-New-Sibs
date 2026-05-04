"""Card suspension and deck-ignoring helpers for the SibPush workflow."""

from __future__ import annotations

from collections.abc import Sequence

from anki.cards import Card
from anki.collection import Collection

from ..state import SUSPENDED_BY_ADDON_TAG
from .query import get_deck_rule


def suspend_cards(col: Collection, cards_to_suspend: Sequence[Card], note_id: int) -> None:
    """Suspend a group of cards and mark their note as managed by the add-on.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.
        cards_to_suspend (Sequence[anki.cards.Card]): The cards to suspend.
        note_id (int): The note id associated with the cards.

    Returns:
        None: The operation is performed for its side effects.
    """

    if not cards_to_suspend:
        return

    note = cards_to_suspend[0].note()

    if not note.has_tag(SUSPENDED_BY_ADDON_TAG):
        # Add tag to mark the note as managed by the addon, if already added, it won't be duplicated.
        note.add_tag(SUSPENDED_BY_ADDON_TAG)
        col.update_note(note)

    col.sched.suspend_cards([card.id for card in cards_to_suspend])


def note_is_ignored_deck(card: Card) -> bool:
    """Return whether a card belongs to a deck marked as ignored.

    Args:
        card (anki.cards.Card): The card to inspect.

    Returns:
        bool: True when the card's deck is configured to be ignored.
    """

    rule = get_deck_rule(card)
    return bool(rule and rule.get("ignored"))
