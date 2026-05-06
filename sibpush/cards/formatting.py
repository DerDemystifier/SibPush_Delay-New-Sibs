"""Human-readable card and note formatting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TYPE_CHECKING

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

from .snapshots import CardSnapshot, capture_snapshots

if TYPE_CHECKING:
    from anki.collection import Collection


def _deck_name_for_card(col: Collection, card: Card) -> str:
    """Return the deck name for a card, or a fallback label when missing.

    Args:
        col (anki.collection.Collection): The collection that owns the card.
        card (anki.cards.Card): The card whose deck name should be resolved.

    Returns:
        str: The resolved deck name or "Unknown Deck" when the deck cannot be found.
    """

    deck = col.decks.get(card.did)
    if not deck:
        return "Unknown Deck"
    return str(deck.get("name", "Unknown Deck"))


def _status_label(queue: int, card_type: int) -> str:
    """Convert Anki queue/type codes into a readable status label.

    Args:
        queue (int): The card queue value.
        card_type (int): The card type value.

    Returns:
        str: A human-readable status label for the card.
    """

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
    """Render the interval text appropriate for the card state.

    Args:
        queue (int): The card queue value.
        card_type (int): The card type value.
        ivl (int): The card interval value.

    Returns:
        str: A compact interval string suitable for debug output.
    """

    if queue in {QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_MANUALLY_BURIED, QUEUE_TYPE_SIBLING_BURIED}:
        return "—"
    if card_type == CARD_TYPE_NEW:
        return "new"
    if queue == QUEUE_TYPE_LRN:
        return f"{ivl} steps"
    return f"{ivl}d"


def _sort_key(snapshot: CardSnapshot) -> tuple[int, int, int, int]:
    """Sort snapshots into review, new, and buried groups.

    Args:
        snapshot (CardSnapshot): The snapshot to order.

    Returns:
        tuple[int, int, int, int]: A stable sort key for log rendering.
    """

    # Group cards in the order most readers care about first: review cards, then new cards,
    # then buried/suspended cards, with due/id/interval used as stable tie-breakers.
    if snapshot.queue in {
        QUEUE_TYPE_SUSPENDED,
        QUEUE_TYPE_MANUALLY_BURIED,
        QUEUE_TYPE_SIBLING_BURIED,
    }:
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
    """Format a single card snapshot line for debug output.

    Args:
        snapshot (CardSnapshot): The snapshot to render.
        previous_status (str | None): The previous status label, when comparing before/after.
        indent (str): The indentation prefix to use for the rendered line.

    Returns:
        str: A formatted log line for the snapshot.
    """

    status = _status_label(snapshot.queue, snapshot.type)
    interval = _interval_label(snapshot.queue, snapshot.type, snapshot.ivl)
    suffix = f" (was {previous_status})" if previous_status and previous_status != status else ""
    return f"{indent}--- Card {snapshot.id} | Due: {snapshot.due} | Interval: {interval} [{status}]{suffix}"


def _format_note_header(note: Any, col: Collection, note_id: int) -> list[str]:
    """Build the header lines for a note's log block.

    Args:
        note (Any): The Anki note to summarize.
        col (anki.collection.Collection): The collection containing the note.
        note_id (int): The note identifier to display.

    Returns:
        list[str]: The header lines for the rendered note block.
    """

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
    snapshots: list[CardSnapshot] | tuple[CardSnapshot, ...] | Sequence[CardSnapshot],
    section: str | None = None,
    previous_statuses: dict[int, str] | None = None,
    include_header: bool = True,
) -> str:
    """Render a note snapshot with optional section labeling.

    Args:
        note (Any): The note being rendered.
        col (anki.collection.Collection): The collection containing the note.
        note_id (int): The note identifier to display.
        snapshots (Sequence[CardSnapshot]): The card snapshots to render.
        section (str | None): Optional section heading such as "Before" or "After".
        previous_statuses (dict[int, str] | None): Optional previous status labels keyed by card id.
        include_header (bool): Whether to include the note header lines.

    Returns:
        str: A formatted multi-line log block for the note.
    """

    lines = _format_note_header(note, col, note_id) if include_header else []
    if section:
        lines.append(f"    {section}:")

    indent = "      " if section else "    "
    for snapshot in sorted(snapshots, key=_sort_key):
        previous_status = previous_statuses.get(snapshot.id) if previous_statuses else None
        lines.append(
            _format_snapshot_line(snapshot, previous_status=previous_status, indent=indent)
        )

    return "\n".join(lines)


def format_note_change(
    note: Any,
    col: Collection,
    note_id: int,
    before_snapshots: list[CardSnapshot] | tuple[CardSnapshot, ...] | Sequence[CardSnapshot],
    after_snapshots: list[CardSnapshot] | tuple[CardSnapshot, ...] | Sequence[CardSnapshot],
    action: str,
) -> str:
    """Render the before/action/after view of a note mutation.

    Args:
        note (Any): The note being rendered.
        col (anki.collection.Collection): The collection containing the note.
        note_id (int): The note identifier to display.
        before_snapshots (Sequence[CardSnapshot]): The snapshots captured before mutation.
        after_snapshots (Sequence[CardSnapshot]): The snapshots captured after mutation.
        action (str): The description of the action that was taken.

    Returns:
        str: The formatted log block describing the change.
    """

    # Capture the before-state labels up front so the "After" section can annotate cards
    # whose status changed during the mutation.
    before_statuses = {
        snapshot.id: _status_label(snapshot.queue, snapshot.type) for snapshot in before_snapshots
    }
    lines = _format_note_header(note, col, note_id)
    lines.append(
        format_note_snapshot(
            note, col, note_id, before_snapshots, section="Before", include_header=False
        )
    )
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
    """Return a one-line summary for a single card.

    Args:
        card (anki.cards.Card): The card to describe.

    Returns:
        str: A compact, human-readable card summary.
    """

    status = _status_label(card.queue, card.type)
    interval = _interval_label(card.queue, card.type, card.ivl)
    return f"    --- Card {card.id} | Due: {card.due} | Interval: {interval} [{status}]"


def cards_details(
    cards: Sequence[Card], col: Collection | None = None, note_id: int | None = None
) -> str:
    """Format a sibling group for readable debug logging.

    Args:
        cards (Sequence[anki.cards.Card]): The cards to render.
        col (anki.collection.Collection | None): The collection for richer note-aware output.
        note_id (int | None): Optional note identifier to display when a collection is provided.

    Returns:
        str: The formatted card summary block, or "(no cards)" when the input is empty.
    """

    if not cards:
        return "(no cards)"

    if col is None:
        return "\n".join(card_details(card) for card in cards)

    note = cards[0].note()
    display_note_id = note_id if note_id is not None else getattr(note, "id", "unknown")
    snapshots = capture_snapshots(cards)
    return format_note_snapshot(note, col, display_note_id, snapshots)
