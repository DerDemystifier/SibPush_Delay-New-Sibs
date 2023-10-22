import os
from pathlib import Path
from aqt.utils import tooltip
from aqt import mw
from aqt import gui_hooks, deckbrowser
from typing import Collection, Sequence, Callable
from anki.cards import Card
import anki
from datetime import datetime


import sys

from .helper import (
    cards_details,
    classify_cards,
    conf_debug,
    conf_ignored_decks,
)
import logging

addon_path = os.path.dirname(os.path.realpath(__file__))

LOG_FILE = os.path.join(addon_path, "log.txt")
# Configure the logging setup
logging.basicConfig(filename=LOG_FILE, level=logging.DEBUG, encoding="UTF-8")


def get_new_note_ids(col: anki.collection.Collection) -> list[int]:
    """Get the ids of all new notes in the collection. While ignoring the decks specified in the config.

    Args:
        col (anki.collection.Collection): The collection to search in.

    Returns:
        list[int] : The list of nids of the found Notes.
    """
    # ["abc", "efg"] → "-deck:abc -deck:efg"
    ignored_decks_query = " ".join(
        [f"-deck:{deck}" for deck in conf_ignored_decks if deck]
    )
    return col.find_notes(f"is:new {ignored_decks_query}")


def get_new_unburied_cardIds(col: anki.collection.Collection) -> list[int]:
    """Get the ids of all new unburied cards in the collection. While ignoring the decks specified in the config.

    Args:
        col (anki.collection.Collection): The collection to search in.

    Returns:
        list[int] : The list of ids of the found cards.
    """
    # ["abc", "efg"] → "-deck:abc -deck:efg"
    ignored_decks_query = " ".join(
        [f"-deck:{deck}" for deck in conf_ignored_decks if deck]
    )
    return col.find_cards(f"is:new -is:buried {ignored_decks_query}")


def get_siblings(note_id: int) -> Sequence[Card]:
    """Get all cards of a note.

    Args:
        note_id (int): The id of the note to search for.

    Returns:
        Sequence[Card]: The list of cards of the note.
    """
    card_ids = mw.col.db.list("select id from cards where nid=?", note_id)
    return [mw.col.get_card(card_id) for card_id in card_ids]


unburied_cards_ids = []


def start_work(col: anki.collection.Collection):
    """This is the main function. Start the work when the collection is loaded.

    Args:
        col (anki.collection.Collection): The collection to work on.
    """

    # start check ... This is to prevent the function from running multiple times on the same new cards, so only run if the user has added new cards or unburied cards since the last time this function was called
    global unburied_cards_ids
    temp = get_new_unburied_cardIds(col)
    if len(temp) == len(unburied_cards_ids):
        return
    unburied_cards_ids = temp
    # end check

    new_note_ids = get_new_note_ids(col)

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


# @gui_hooks.collection_did_load.append
# def collection_did_load(col: anki.collection.Collection):
#     logThis("collection_did_load hook triggered!")
#     start_work(col)


@gui_hooks.deck_browser_did_render.append
def browser_render(browser: deckbrowser.DeckBrowser):
    logThis("deck_browser_did_render hook triggered!")
    start_work(browser.mw.col)


def logThis(arg, clear=False):
    if conf_debug:
        message = arg() if callable(arg) else arg

        # Clear the log file if the 'clear' flag is set
        if clear:
            with open(LOG_FILE, "w", encoding="UTF-8") as f:
                pass  # This will clear the file

        # Log the message using Python's logging module
        logging.debug(message)


logThis(
    str(datetime.today())
    + """
# Legend for card details:
#   Type: 0=new, 1=learning, 2=due
#   Queue: same as above, and:
#       -1=suspended, -2=user buried, -3=sched buried
#   Due is used differently for different queues.
#       new queue: position
#       rev queue: integer day
#       lrn queue: integer timestamp
""",
    True,
)
