"""Query and caching helpers for the SibPush note workflow."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from anki.cards import Card
from anki.collection import Collection
from anki.notes import Note, NoteId

from ..config.parser import config_settings, custom_deck_rules_by_did, ignored_deck_ids
from ..state import get_last_checked_state, get_mw


def get_tag_rule(note: Note) -> dict[str, Any] | None:
    """Look up the first matching tag rule for a note.

    Args:
        note (anki.notes.Note): The note whose tags should be inspected.

    Returns:
        dict[str, Any] | None: The matching rule, or None when no tag rule applies.
    """

    raw_tag_rules = config_settings.get("tag_rules", {})
    if not isinstance(raw_tag_rules, dict):
        return None

    note_tags = {str(tag).strip() for tag in getattr(note, "tags", []) if str(tag).strip()}
    for raw_tag, rule in raw_tag_rules.items():
        tag = str(raw_tag).strip()
        if tag and tag in note_tags and isinstance(rule, dict):
            return rule

    return None


def get_new_note_ids(col: Collection) -> Sequence[NoteId]:
    """Return the ids of all new notes that are not in ignored decks.

    Args:
        col (anki.collection.Collection): The collection to search.

    Returns:
        Sequence[anki.notes.NoteId]: The ids of the matching new notes.
    """

    ignored_query = " ".join(f"-did:{deck_id}" for deck_id in ignored_deck_ids if deck_id)
    query = f"is:new {ignored_query}".strip()
    return col.find_notes(query)


def get_deck_rule(card: Card) -> dict[str, Any] | None:
    """Look up the custom deck rule associated with a card's deck.

    Args:
        card (anki.cards.Card): The card whose deck rule should be resolved.

    Returns:
        dict[str, Any] | None: The matching rule, or None when no rule exists.
    """

    return custom_deck_rules_by_did.get(str(card.did))


def get_deck_interval(card: Card) -> int:
    """Return the effective interval threshold for a card's deck.

    Args:
        card (anki.cards.Card): The card whose deck interval should be resolved.

    Returns:
        int: The configured interval threshold for the card's deck.
    """

    rule = get_deck_rule(card)
    if rule is None:
        return int(config_settings["default_interval"])

    return int(rule["interval"])


def get_note_interval(note: Note, card: Card) -> int:
    """Return the effective interval threshold for a note.

    Tag rules take precedence over deck rules, and the first matching tag rule in the config wins.

    Args:
        note (anki.notes.Note): The note whose tags should be inspected.
        card (anki.cards.Card): A card from the note used to resolve the deck rule fallback.

    Returns:
        int: The configured interval threshold for the note.
    """

    tag_rule = get_tag_rule(note)
    if tag_rule is not None:
        return int(tag_rule["interval"])

    return get_deck_interval(card)


def get_child_cards(col: Collection, note_id: int) -> Sequence[Card]:
    """Return all sibling cards belonging to a note.

    Args:
        col (anki.collection.Collection): The collection to search.
        note_id (int): The note identifier to fetch cards for.

    Returns:
        Sequence[anki.cards.Card]: The cards belonging to the note.
    """

    card_ids = col.find_cards(query=f"nid:{note_id}")
    current_mw = get_mw()
    if not current_mw or not current_mw.col or not current_mw.col.db:
        raise Exception("SibPush : Anki is not initialized properly")

    # You can also conduct searches using the db connection directly.
    # card_ids = mw.col.db.list("select id from cards where nid=?", note_id)
    return [current_mw.col.get_card(card_id) for card_id in card_ids]


def should_run_work(col: Collection) -> tuple[bool, tuple[str, Sequence[NoteId]]]:
    """Decide whether the batch note-processing pass should run.

    Args:
        col (anki.collection.Collection): The collection to inspect for new notes.

    Returns:
        tuple[bool, tuple[str, Sequence[anki.notes.NoteId]]]: A tuple containing a boolean flag
            indicating whether work should run and the current cache state.
    """

    today = date.today().isoformat()
    current_new_note_ids = get_new_note_ids(col)
    last_checked_state = get_last_checked_state()

    if last_checked_state is None:
        return True, (today, current_new_note_ids)

    # Compare the current state with the last checked state to decide whether to run the processing.
    last_checked_date, last_checked_new_note_ids = last_checked_state
    should_run = last_checked_date != today or last_checked_new_note_ids != current_new_note_ids

    return should_run, (today, current_new_note_ids)
