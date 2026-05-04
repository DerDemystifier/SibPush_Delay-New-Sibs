"""
Utilities for creating note types, decks, and adding notes in a test collection.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.cards import Card
    from anki.collection import Collection
    from anki.decks import DeckId
    from anki.models import NotetypeDict
    from anki.notes import Note


TEST_NOTE_TYPE_NAME = "SibPush Test Note"
TEST_DECK_NAME = "SibPush Test Deck"


def make_test_deck_id(col: "Collection") -> "DeckId":
    """Ensure the test deck exists and return its ID."""
    deck_id = col.decks.id(TEST_DECK_NAME)
    assert deck_id is not None
    return deck_id


def build_test_notetype(col: "Collection", card_count: int = 3) -> "NotetypeDict":
    """
    Create a simple note type with a configurable number of sibling cards for testing.
    """
    model = col.models.new(TEST_NOTE_TYPE_NAME)
    col.models.add_field(model, col.models.new_field("Front"))

    # Create templates to ensure we have siblings to manage
    for idx in range(card_count):
        template = col.models.new_template(f"Card {idx + 1}")
        template["qfmt"] = f"{{{{Front}}}}<div>Card {idx + 1}</div>"
        template["afmt"] = f"{{{{Front}}}}<hr id='answer'>Card {idx + 1}"
        col.models.add_template(model, template)

    col.models.add(model)
    return col.models.get(model["id"]) or model


def add_note_with_siblings(
    col: "Collection",
    model: "NotetypeDict",
    deck_id: "DeckId",
    front_text: str,
    expected_card_count: int = 3,
) -> tuple["Note", Sequence["Card"]]:
    """
    Add a new note to the collection and return it along with its cards.
    """
    note = col.new_note(model)
    note["Front"] = front_text
    col.add_note(note, deck_id)

    cards = note.cards()
    assert len(cards) == expected_card_count, f"expected the test note type to generate {expected_card_count} cards"
    return note, cards
