from typing import Sequence
from anki.cards import Card


# This function takes an array of cards and calls card_details on each of them
def cards_details(cards: Sequence[Card]) -> str:
    return "[\n" + "\n".join([card_details(card) for card in cards]) + "\n]"


def card_details(card: Card) -> str:
    return f"card.id: {card.id} card.queue:{card.queue} card.type:{card.type} card.ivl:{card.ivl} card.due:{card.due} card.deckID:{card.did} card.flags:{card.flags}"
