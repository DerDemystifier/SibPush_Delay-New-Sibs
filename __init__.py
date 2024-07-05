import logging
import os
from aqt import mw
from aqt import gui_hooks, deckbrowser
from aqt.addons import AddonsDialog
from typing import Sequence, cast
from anki.cards import Card
from anki.collection import Collection, BrowserColumns
from anki.notes import NoteId
from .log_helper import logThis, initialize_log_file
from .helper import (
    cards_details,
    classify_cards,
)
from .config_parser import config_settings, on_config_save


addon_path = os.path.dirname(os.path.realpath(__file__))


def get_new_note_ids(col: Collection) -> Sequence[NoteId]:
    """Get the ids of all new notes in the collection. While ignoring the decks specified in the config.

    Args:
        col (anki.collection.Collection): The collection to search in.

    Returns:
        list[int] : The list of nids of the found Notes.
    """
    # ["abc", "efg"] → "-deck:abc -deck:efg"
    ignored_decks_query = " ".join(
        [
            f'-deck:"{deck}"'
            for deck in cast(str, config_settings["ignored_decks"])
            if deck
        ]
    )
    return col.find_notes(f"is:new -is:suspended {ignored_decks_query}")


def get_siblings(note_id: int) -> Sequence[Card]:
    """Get all cards of a note.

    Args:
        note_id (int): The id of the note to search for.

    Returns:
        Sequence[Card]: The list of cards of the note.
    """

    if not mw or not mw.col or not mw.col.db:
        raise Exception("SibPush : Anki is not initialized properly")

    card_ids = mw.col.find_cards(query=f"nid:{note_id}", order=due_column)

    # You can also conduct searches using the db connection directly
    # card_ids = mw.col.db.list("select id from cards where nid=?", note_id)

    return [mw.col.get_card(card_id) for card_id in card_ids]


new_note_ids: Sequence[NoteId] = []
due_column: BrowserColumns.Column


def start_work(col: Collection):
    """This is the main function. Start the work when the collection is loaded.

    Args:
        col (anki.collection.Collection): The collection to work on.
    """

    # start check ... This is to prevent the function from running multiple times on the same new cards, so only run if the user has added new cards since the last time this function was called
    global new_note_ids, due_column

    temp = get_new_note_ids(col)
    if len(temp) <= len(new_note_ids):
        return
    new_note_ids = temp
    # end check

    if not mw or not mw.col:
        raise Exception("SibPush : Anki is not initialized properly")

    all_browser_columns = mw.col.all_browser_columns()

    # Find the BrowserColumn for the due date
    due_column = next(col for col in all_browser_columns if col.key == "cardDue")

    logThis(f"new_note_ids: {new_note_ids}")
    for new_note_id in new_note_ids:
        siblings = get_siblings(new_note_id)

        if len(siblings) <= 1:
            # If the note has only one card, there move on
            continue

        logThis(
            lambda: f"`Siblings within nid:{new_note_id} → {cards_details(siblings)}"
        )

        new_cards, learning_cards = classify_cards(siblings)

        if not mw or not mw.col or not mw.col.sched:
            raise Exception("SibPush : Anki is not initialized properly")

        if learning_cards:
            # Since there are learning cards of the same note, bury all new cards, minus those already buried

            cards_to_bury = [card for card in new_cards if card.queue >= 0]

            if not cards_to_bury:
                # If all cards to bury are already buried, then this list is empty anyway
                continue

            logThis(
                lambda: f"\t\tBurying all new cards from nid:{new_note_id} →: {cards_details(cards_to_bury)}\n"
            )

            card_ids_to_bury = [card.id for card in cards_to_bury]
            mw.col.sched.bury_cards(card_ids_to_bury, manual=True)
        else:
            # No learning cards, leave one new card for the user to study and bury the rest

            # only count the new cards that are not buried, then leave one to bury the rest
            cards_to_bury = [card for card in new_cards if card.queue >= 0][1:]

            if not cards_to_bury:
                # If there was only one new card in the note, then this list is empty anyway
                continue

            logThis(
                lambda: f"\t\tBurying some new cards from nid:{new_note_id} →: {cards_details(cards_to_bury)}\n"
            )

            card_ids_to_bury = [card.id for card in cards_to_bury]
            mw.col.sched.bury_cards(card_ids_to_bury, manual=True)


@gui_hooks.collection_did_load.append
def collection_did_load(col: Collection):
    initialize_log_file()


@gui_hooks.deck_browser_did_render.append
def browser_render(browser: deckbrowser.DeckBrowser):
    logThis("deck_browser_did_render hook triggered!")
    start_work(browser.mw.col)


gui_hooks.addon_config_editor_will_update_json.append(on_config_save)


@gui_hooks.addons_dialog_will_delete_addons.append
def on_addon_delete(dialog: AddonsDialog, ids: list[str]):
    logging.shutdown()
