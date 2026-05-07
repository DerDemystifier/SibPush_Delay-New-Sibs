from __future__ import annotations

from importlib import import_module

from ..addon_utils import patched_addon_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id


def _set_note_mod(col: object, note_id: int, timestamp: int) -> None:
    col.db.execute(f"UPDATE notes SET mod = {timestamp} WHERE id = {note_id}")


def _set_card_mod(col: object, card_id: int, timestamp: int) -> None:
    col.db.execute(f"UPDATE cards SET mod = {timestamp} WHERE id = {card_id}")


def test_get_modified_note_ids_since_combines_note_and_card_changes_without_duplicates() -> None:
    """
    Scenario: The modified-note query should combine note-row and card-row timestamps.

    A note edited via `notes.mod`, another note edited via `cards.mod`, and a third note edited
    through both paths should all be returned once, with no duplicate note ids in the result.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        note_mod_note, note_mod_cards = add_note_with_siblings(
            col, model, deck_id, "Note-row modified note"
        )
        card_mod_note, card_mod_cards = add_note_with_siblings(
            col, model, deck_id, "Card-row modified note"
        )
        combined_note, combined_cards = add_note_with_siblings(
            col, model, deck_id, "Combined note and card modified note"
        )
        untouched_note, untouched_cards = add_note_with_siblings(
            col, model, deck_id, "Untouched note"
        )

        for note, cards in (
            (note_mod_note, note_mod_cards),
            (card_mod_note, card_mod_cards),
            (combined_note, combined_cards),
            (untouched_note, untouched_cards),
        ):
            _set_note_mod(col, note.id, 100)
            for card in cards:
                _set_card_mod(col, card.id, 100)

        _set_note_mod(col, note_mod_note.id, 250)
        _set_card_mod(col, card_mod_cards[1].id, 300)
        _set_note_mod(col, combined_note.id, 400)
        _set_card_mod(col, combined_cards[2].id, 450)

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            query_module = import_module(f"{addon.__name__}.sibpush.processing.query")

            modified_note_ids = query_module.get_modified_note_ids_since(col, 150)

        assert len(modified_note_ids) == 3
        assert len(modified_note_ids) == len(set(modified_note_ids))
        assert set(modified_note_ids) == {note_mod_note.id, card_mod_note.id, combined_note.id}


if __name__ == "__main__":
    test_get_modified_note_ids_since_combines_note_and_card_changes_without_duplicates()
