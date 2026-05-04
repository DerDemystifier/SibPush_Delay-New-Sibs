from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, TYPE_CHECKING, cast

from anki.cards import (
    CARD_TYPE_NEW,
    QUEUE_TYPE_LRN,
    QUEUE_TYPE_MANUALLY_BURIED,
    QUEUE_TYPE_NEW,
    QUEUE_TYPE_REV,
    QUEUE_TYPE_SIBLING_BURIED,
    QUEUE_TYPE_SUSPENDED,
    Card,
)

from .config_parser import config_settings

if TYPE_CHECKING:
    from anki.collection import Collection


@dataclass(frozen=True)
class CardSnapshot:
    id: int
    queue: int
    type: int
    ivl: int
    due: int
    did: int
    flags: int


def _deck_name_for_card(col: Collection, card: Card) -> str:
    deck = cast(Optional[dict[str, Any]], col.decks.get(card.did))
    if not deck:
        return "Unknown Deck"
    return str(deck.get("name", "Unknown Deck"))


def _deck_name_for_snapshot(col: Collection, snapshot: CardSnapshot) -> str:
    deck = cast(Optional[dict[str, Any]], col.decks.get(snapshot.did))
    if not deck:
        return "Unknown Deck"
    return str(deck.get("name", "Unknown Deck"))


def capture_snapshots(cards: Sequence[Card]) -> list[CardSnapshot]:
    """Capture the card state before it mutates so it can be rendered later."""

    return [
        CardSnapshot(
            id=card.id,
            queue=card.queue,
            type=card.type,
            ivl=card.ivl,
            due=card.due,
            did=card.did,
            flags=card.flags,
        )
        for card in cards
    ]


def _status_label(queue: int, card_type: int) -> str:
    if queue == QUEUE_TYPE_SUSPENDED:
        return "SUSPENDED"
    if queue == QUEUE_TYPE_MANUALLY_BURIED:
        return "MANUALLY BURIED"
    if queue == QUEUE_TYPE_SIBLING_BURIED:
        return "SIBLING BURIED"
    if card_type == CARD_TYPE_NEW or queue == QUEUE_TYPE_NEW:
        return "NEW"
    if queue == QUEUE_TYPE_LRN:
        return "LEARNING"
    if queue == QUEUE_TYPE_REV:
        return "REVIEW"
    return f"QUEUE {queue}"


def _interval_label(queue: int, card_type: int, ivl: int) -> str:
    if queue in {QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED}:
        return "—"
    if card_type == CARD_TYPE_NEW:
        return "new"
    if queue == QUEUE_TYPE_LRN:
        return f"{ivl} steps"
    return f"{ivl}d"


def _sort_key(snapshot: CardSnapshot) -> tuple[int, int, int, int]:
    if snapshot.queue in {QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED}:
        group = 2
        return group, snapshot.due, snapshot.id, snapshot.ivl

    if snapshot.type == CARD_TYPE_NEW or snapshot.queue == QUEUE_TYPE_NEW:
        group = 1
        return group, snapshot.due, snapshot.id, snapshot.ivl

    group = 0
    return group, -snapshot.ivl, snapshot.due, snapshot.id


def _format_snapshot_line(
    snapshot: CardSnapshot,
    previous_status: str | None = None,
    indent: str = "      ",
) -> str:
    status = _status_label(snapshot.queue, snapshot.type)
    interval = _interval_label(snapshot.queue, snapshot.type, snapshot.ivl)
    suffix = f" (was {previous_status})" if previous_status and previous_status != status else ""
    return f"{indent}--- Card {snapshot.id} | Due: {snapshot.due} | Interval: {interval} [{status}]{suffix}"


def _format_note_header(note: Any, col: Collection, note_id: int) -> list[str]:
    note_type = note.note_type()
    model_name = str(note_type.get("name", "Unknown")) if note_type else "Unknown"
    tags = ", ".join(str(tag) for tag in getattr(note, "tags", [])) or "none"
    deck_names = sorted({_deck_name_for_card(col, card) for card in note.cards()})
    deck_display = deck_names[0] if len(deck_names) == 1 else ", ".join(deck_names)
    return [f'Deck: "{deck_display}"', f"  Note {note_id} (Model: {model_name}, Tags: {tags}):"]


def format_note_snapshot(
    note: Any,
    col: Collection,
    note_id: int,
    snapshots: Sequence[CardSnapshot],
    section: str | None = None,
    previous_statuses: dict[int, str] | None = None,
    include_header: bool = True,
) -> str:
    """Render one note snapshot in a compact readable block."""

    lines = _format_note_header(note, col, note_id) if include_header else []
    if section:
        lines.append(f"    {section}:")

    indent = "      " if section else "    "
    for snapshot in sorted(snapshots, key=_sort_key):
        previous_status = previous_statuses.get(snapshot.id) if previous_statuses else None
        lines.append(_format_snapshot_line(snapshot, previous_status=previous_status, indent=indent))

    return "\n".join(lines)


def format_note_change(
    note: Any,
    col: Collection,
    note_id: int,
    before_snapshots: Sequence[CardSnapshot],
    after_snapshots: Sequence[CardSnapshot],
    action: str,
) -> str:
    """Render a before/action/after block for a note processing step."""

    before_statuses = {snapshot.id: _status_label(snapshot.queue, snapshot.type) for snapshot in before_snapshots}
    lines = _format_note_header(note, col, note_id)
    lines.append(format_note_snapshot(note, col, note_id, before_snapshots, section="Before", include_header=False))
    lines.append(f"    Action: {action}")
    lines.append(
        format_note_snapshot(
            note,
            col,
            note_id,
            after_snapshots,
            section="After",
            previous_statuses=before_statuses,
            include_header=False,
        )
    )
    return "\n".join(lines)


def card_details(card: Card) -> str:
    """Return a concise, human-readable summary for a single card."""

    status = _status_label(card.queue, card.type)
    interval = _interval_label(card.queue, card.type, card.ivl)
    return f"    --- Card {card.id} | Due: {card.due} | Interval: {interval} [{status}]"


def cards_details(cards: Sequence[Card], col: Optional[Collection] = None, note_id: int | None = None) -> str:
    """Format a group of sibling cards for readable debug logging."""

    if not cards:
        return "(no cards)"

    if col is None:
        return "\n".join(card_details(card) for card in cards)

    note = cards[0].note()
    display_note_id = note_id if note_id is not None else getattr(note, "id", "unknown")
    snapshots = capture_snapshots(cards)
    return format_note_snapshot(note, col, display_note_id, snapshots)


def classify_cards(siblings: Sequence[Card]) -> tuple[list[Card], list[Card]]:
    """Classify cards into new and immature cards.

    Args:
        siblings (Sequence[Card]): The cards to classify

    Returns:
        tuple: A tuple of two lists. The first list contains the new cards, the second list contains the immature cards.
    """
    new_cards: list[Card] = []
    immature_cards: list[Card] = []
    for sibling in siblings:
        if sibling.queue == QUEUE_TYPE_SUSPENDED:
            # This means the card is suspended, so we don't care about it
            continue

        if sibling.type == CARD_TYPE_NEW:
            new_cards.append(sibling)
        elif sibling.ivl < config_settings["interval"]:
            immature_cards.append(sibling)

    return new_cards, immature_cards
