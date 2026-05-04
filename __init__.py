import logging
import os
from datetime import date
from aqt import mw
from aqt import gui_hooks
from typing import Any, Sequence, cast
from anki.cards import Card
from anki.collection import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED, Collection
from anki.notes import NoteId
from .log_helper import logThis, initialize_log_file
from .helper import (
    cards_details,
    classify_cards,
)
from .config_parser import config_settings, on_config_save

addon_path = os.path.dirname(os.path.realpath(__file__))
SUSPENDED_BY_ADDON_TAG = "SibPush-suspended"


def get_ignored_decks_query() -> str:
    """Build the deck exclusion query from the addon config."""

    return " ".join(
        [f'-deck:"{deck}"' for deck in cast(list[str], config_settings["ignored_decks"]) if deck]
    )


def get_new_note_ids(col: Collection) -> Sequence[NoteId]:
    """Get the ids of all new notes in the collection. While ignoring the decks specified in the config.

    Args:
        col (anki.collection.Collection): The collection to search in.

    Returns:
        list[int] : The list of nids of the found Notes.
    """
    ignored_decks_query = get_ignored_decks_query()
    return col.find_notes(f"is:new {ignored_decks_query}")


def get_child_cards(col: Collection, note_id: int) -> Sequence[Card]:
    """Get all child cards of a note.

    Args:
        note_id (int): The id of the note to search for.

    Returns:
        Sequence[Card]: The list of child cards of the note.
    """

    if not mw or not mw.col or not mw.col.db:
        raise Exception("SibPush : Anki is not initialized properly")

    card_ids = col.find_cards(query=f"nid:{note_id}")

    # You can also conduct searches using the db connection directly
    # card_ids = mw.col.db.list("select id from cards where nid=?", note_id)

    return [mw.col.get_card(card_id) for card_id in card_ids]


last_checked_state: tuple[str, Sequence[NoteId]] | None = None


def should_run_work(col: Collection) -> tuple[bool, tuple[str, Sequence[NoteId]]]:
    """Determine whether the addon should run the processing of notes in the current hook call.

    The addon should run the processing of notes if either the date has changed since the last check (for users who never close Anki), or if there are new notes that were just added. This is to avoid unnecessary processing on every render pass.

    Args:
        col (anki.collection.Collection): The collection to check for new notes.
    Returns:
        tuple[bool, tuple[str, Sequence[NoteId]]]: A tuple where the first element is a boolean indicating whether to run the processing, and the second element is the current state (**current date** and **list of new note ids**) to be used for future comparisons.
    """

    today = date.today().isoformat()
    current_new_note_ids = get_new_note_ids(col)

    if last_checked_state is None:
        return True, (today, current_new_note_ids)

    # Compare the current state with the last checked state to decide whether to run the processing
    last_checked_date, last_checked_new_note_ids = last_checked_state
    should_run = last_checked_date != today or last_checked_new_note_ids != current_new_note_ids

    return should_run, (today, current_new_note_ids)


def suspend_cards(col: Collection, cards_to_suspend: Sequence[Card], note_id: int):
    """Suspend the given cards and mark their note as addon-managed."""

    if not cards_to_suspend:
        return

    note = cards_to_suspend[0].note()
    logThis(
        lambda: f"\t\tSuspending new cards from nid:{note_id} →: {cards_details(cards_to_suspend)}\n"
    )

    col.sched.suspend_cards([card.id for card in cards_to_suspend])

    note.add_tag(
        SUSPENDED_BY_ADDON_TAG
    )  # Add tag to mark the note as managed by the addon, if already added, it won't be duplicated
    col.update_note(note)


def note_is_ignored_deck(col: Collection, card: Card) -> bool:
    """Return whether the card belongs to one of the ignored decks."""

    ignored_decks = {
        str(deck) for deck in cast(list[str], config_settings["ignored_decks"]) if deck
    }
    if not ignored_decks:
        return False

    deck = cast(dict[str, Any], col.decks.get(card.did))
    deck_name = str(deck.get("name", ""))
    return deck_name in ignored_decks or str(card.did) in ignored_decks


def process_note(col: Collection, note_id: int, coming_from_reviewer_hook: bool = False):
    """Process the cards belonging to a single note."""

    siblings = get_child_cards(col, note_id)
    siblings = sorted(
        siblings, key=lambda card: card.due
    )  # Sort siblings by due date to respect the original order of cards.

    if len(siblings) <= 1:
        # If the note has only one card, then move on
        return

    if note_is_ignored_deck(col, siblings[0]):
        return

    logThis(lambda: f"`Siblings within nid:{note_id} → {cards_details(siblings)}")

    all_new_cards = [card for card in siblings if card.type == CARD_TYPE_NEW]
    new_cards, immature_cards = classify_cards(siblings)
    note = siblings[0].note()

    if immature_cards:
        # Since there are immature cards in the note, suspend all new cards (if not already suspended by the addon).

        new_cards_to_suspend = [
            card
            for card in new_cards
            if card.queue
            != QUEUE_TYPE_SUSPENDED  # card.queue == QUEUE_TYPE_SUSPENDED means the card is already suspended.
        ]  # We don't want to add the tag (by calling suspend_new_cards()) to a note if all cards are manually suspended.

        if not new_cards_to_suspend:
            # If all cards to suspend are already suspended, then this list is empty anyway
            return

        # if coming_from_reviewer_hook:
        #     first_new_card = new_cards_to_suspend.pop(0)
        #     col.sched.bury_cards(ids=[first_new_card.id], manual=False)

        suspend_cards(col, new_cards_to_suspend, note_id)
    else:
        # No immature cards, keep the first new card available and suspend the rest.

        if not all_new_cards:
            # If new cards list is empty, then there are no new cards to process anymore, so skip to the next note.
            return

        if note.has_tag(SUSPENDED_BY_ADDON_TAG):
            # This means that some new cards of this note were previously suspended by the addon, so we can safely unsuspend the first card and suspend the rest (if not already suspended).
            first_card = all_new_cards[0]
            if first_card.queue == QUEUE_TYPE_SUSPENDED:
                logThis(
                    lambda: f"\t\tUnsuspending first new card from nid:{note_id} →: {cards_details([first_card])}\n"
                )
                col.sched.unsuspend_cards([first_card.id])
                if coming_from_reviewer_hook:
                    col.sched.bury_cards(
                        ids=[first_card.id], manual=False
                    )  # Bury the card to not review right after after unsuspending

            # No need to re-suspend the others; they are already suspended.
        else:
            # If the note is not tagged as addon-managed, this means that this is a new note. So we should bury the first card for tomorrow and suspend the rest (if not already suspended).

            new_cards_to_suspend = [
                card for card in all_new_cards[1:] if card.queue != QUEUE_TYPE_SUSPENDED
            ]
            # first_active_index = next(
            #     (index for index, card in enumerate(all_new_cards) if card.queue != QUEUE_TYPE_SUSPENDED),
            #     None,
            # )

            # if first_active_index is None:
            #     continue

            # cards_to_suspend = [
            #     card for card in all_new_cards[first_active_index + 1 :] if card.queue != QUEUE_TYPE_SUSPENDED
            # ]

            if not new_cards_to_suspend:
                return

            if coming_from_reviewer_hook:
                # This means we've just seen the card that has just matured, so we should bury the next new card for tomorrow to not review right after.
                first_new_card = all_new_cards[0]
                col.sched.bury_cards(
                    ids=[first_new_card.id], manual=False
                )  # Bury the first card for tomorrow to not review right after.

            suspend_cards(col, new_cards_to_suspend, note_id)


def process_all_notes(col: Collection):
    """This is the main function. Start the work when the collection is loaded.

    Args:
        col (anki.collection.Collection): The collection to work on.
    """

    global last_checked_state

    should_run, current_state = should_run_work(col)
    if not should_run:
        # No need to run the processing again on this render pass.
        return

    new_note_ids = current_state[1]

    if not mw or not mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    logThis(f"new_note_ids: {new_note_ids}")

    for new_note_id in new_note_ids:
        process_note(col, new_note_id)

    last_checked_state = current_state


@gui_hooks.collection_did_load.append  # type: ignore
def collection_did_load(col: Collection):
    initialize_log_file()


@gui_hooks.deck_browser_did_render.append  # type: ignore
def browser_render(browser: Any):
    logThis("deck_browser_did_render hook triggered!")

    if not browser or not browser.mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    process_all_notes(browser.mw.col)


@gui_hooks.reviewer_did_answer_card.append  # type: ignore
def reviewer_did_answer_card(reviewer: Any, card: Card, ease: int):
    logThis(lambda: f"reviewer_did_answer_card hook triggered for nid:{card.nid} ease:{ease}")

    if not reviewer or not reviewer.mw or not reviewer.mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    process_note(reviewer.mw.col, card.nid, coming_from_reviewer_hook=True)


gui_hooks.addon_config_editor_will_update_json.append(on_config_save)


@gui_hooks.addons_dialog_will_delete_addons.append
def on_addon_delete(dialog: Any, ids: list[str]):
    logging.shutdown()
