import json
from typing import Sequence
from anki.cards import Card
from .config_parser import config_settings


# This function takes an array of cards and calls card_details on each of them
def cards_details(cards: Sequence[Card]) -> str:
    return "[\n" + "\n".join([card_details(card) for card in cards]) + "\n]"


def card_details(card: Card) -> str:
    """
    Returns a string representation of the card details.

    Args:
        card (Card): The card object containing the details.

    Returns:
        str: The string representation of the card details.
    """
    card_dict: dict[str, object] = {
        "id": card.id,
        "queue": card.queue,
        "type": card.type,
        "ivl": card.ivl,
        "due": card.due,
        "deckID": card.did,
        "flags": card.flags,
    }
    return json.dumps(card_dict)


def classify_cards(siblings: Sequence[Card]) -> tuple[list[Card], list[Card]]:
    """Classify cards into new and learning cards.

    Args:
        siblings (Sequence[Card]): The cards to classify

    Returns:
        tuple: A tuple of two lists. The first list contains the new cards, the second list contains the learning cards.
    """
    new_cards: list[Card] = []
    learning_cards: list[Card] = []
    for sibling in siblings:
        if sibling.queue == -1:
            # This means the card is suspended, so we don't care about it
            continue

        if sibling.type == 0:
            new_cards.append(sibling)
        elif sibling.ivl < config_settings["interval"]:
            learning_cards.append(sibling)

    return new_cards, learning_cards
