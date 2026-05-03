from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from anki.collection import Collection
    from anki.notes import NoteId


class AnkiDB(Protocol):
    """Protocol for the Anki DB runner to satisfy Pylance."""

    def list(self, sql: str, *args: Any) -> list[Any]: ...


def print_collection_state(col: Collection, header: str = "Collection State") -> None:
    """
    Prints a summary of the notes and cards in the collection for debugging/info.
    """
    print(f"\n--- {header} ---")

    # Get all deck names
    decks = col.decks.all_names_and_ids()

    for deck_name_id in decks:
        deck_name = deck_name_id.name
        deck_id = deck_name_id.id

        # Check if there are any cards in this deck
        card_ids = col.find_cards(f"did:{deck_id}")
        if not card_ids:
            continue

        print(f'\nDeck: "{deck_name}"')

        # Use a protocol cast to inform Pylance about the DB runner's methods
        db = cast(AnkiDB, col.db)
        note_ids = cast(
            "list[NoteId]", db.list(f"select distinct nid from cards where did = {deck_id}")
        )

        for nid in note_ids:
            note = col.get_note(nid)
            if not note:
                continue

            nt = note.note_type()
            nt_name = nt["name"] if nt else "Unknown"

            print(f"  Note {nid} (Model: {nt_name}):")

            # Get cards for this note
            cards = note.cards()
            for card in cards:
                status = ""
                if card.queue == -1:
                    status = " [SUSPENDED]"
                elif card.queue == 0:
                    status = " [NEW]"
                elif card.queue == 2:
                    status = " [REVIEW]"
                elif card.queue == 1:
                    status = " [LEARN]"

                # Interval/Due info
                ivl_info = f"Ivl: {card.ivl}d" if card.type == 2 else "New"
                due_info = f"Due: {card.due}"

                print(f"    --- Card {card.id} | {due_info} | {ivl_info}\t{status}")
    print("-" * (len(header) + 8) + "\n")
