from __future__ import annotations

from importlib import import_module

from ..addon_utils import patched_addon_state
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id


def _set_note_mod(col: object, note_id: int, timestamp: int) -> None:
    col.db.execute(f"UPDATE notes SET mod = {timestamp} WHERE id = {note_id}")


def _set_card_mod(col: object, card_id: int, timestamp: int) -> None:
    col.db.execute(f"UPDATE cards SET mod = {timestamp} WHERE id = {card_id}")


def _seed_note_and_card_mods(col: object, note: object, cards: object, timestamp: int) -> None:
    _set_note_mod(col, note.id, timestamp)
    for card in cards:
        _set_card_mod(col, card.id, timestamp)


def test_get_modified_note_ids_since_returns_recent_note_and_card_changes() -> None:
    """
    Scenario: The delta query should return notes whose note rows or card rows changed recently.

    The helper should merge `notes.mod` and `cards.mod`, exclude ignored decks, and keep the
    result note-based for downstream sibling processing.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        active_deck_id = make_test_deck_id(col)
        ignored_deck_id = col.decks.id("SibPush Ignored Deck")

        old_note, old_cards = add_note_with_siblings(col, model, active_deck_id, "Old note")
        note_mod_note, note_mod_cards = add_note_with_siblings(
            col, model, active_deck_id, "Note-modified note"
        )
        card_mod_note, card_mod_cards = add_note_with_siblings(
            col, model, active_deck_id, "Card-modified note"
        )
        ignored_note, ignored_cards = add_note_with_siblings(
            col, model, ignored_deck_id, "Ignored deck note"
        )

        _seed_note_and_card_mods(col, old_note, old_cards, 100)
        _seed_note_and_card_mods(col, note_mod_note, note_mod_cards, 100)
        _seed_note_and_card_mods(col, card_mod_note, card_mod_cards, 100)
        _seed_note_and_card_mods(col, ignored_note, ignored_cards, 100)

        _set_note_mod(col, note_mod_note.id, 250)
        _set_card_mod(col, card_mod_cards[1].id, 300)
        _set_note_mod(col, ignored_note.id, 400)
        _set_card_mod(col, ignored_cards[0].id, 400)

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            query_module = import_module(f"{addon.__name__}.sibpush.processing.query")

            patched_addon.ignored_deck_ids[:] = [str(ignored_deck_id)]

            modified_note_ids = query_module.get_modified_note_ids_since(col, 150)

        assert set(modified_note_ids) == {note_mod_note.id, card_mod_note.id}


if __name__ == "__main__":
    test_get_modified_note_ids_since_returns_recent_note_and_card_changes()
