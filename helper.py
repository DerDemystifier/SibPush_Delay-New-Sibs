from typing import Sequence
from anki.cards import Card
from aqt import mw

# Get the config object for your addon
config = mw.addonManager.getConfig(__name__)
conf_debug = bool(config["debug"])
conf_interval = int(config["interval"])
conf_ignored_decks = config["ignored_decks"].strip().split(",")

# This function takes an array of cards and calls card_details on each of them
def cards_details(cards: Sequence[Card]) -> str:
    return "[\n" + "\n".join([card_details(card) for card in cards]) + "\n]"


def card_details(card: Card) -> str:
    return f"card.id: {card.id} card.queue:{card.queue} card.type:{card.type} card.ivl:{card.ivl} card.due:{card.due} card.deckID:{card.did} card.flags:{card.flags}"


def classify_cards(siblings):
    new_cards = []
    learning_cards = []
    for sibling in siblings:
        if sibling.queue == -1:
            # This means the card is suspended, so we don't care about it
            continue

        if sibling.type == 0:
            new_cards.append(sibling)
        elif sibling.ivl < conf_interval:
            learning_cards.append(sibling)

    return new_cards, learning_cards
