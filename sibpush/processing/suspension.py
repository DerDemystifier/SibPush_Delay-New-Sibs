"""Card suspension and deck-ignoring helpers for the SibPush workflow."""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from typing import Any, Callable, cast

from anki.cards import CARD_TYPE_NEW, Card, CardId

from ..cards.snapshots import CardSnapshot
from anki.collection import Collection
from anki.consts import QUEUE_TYPE_SUSPENDED
from anki.notes import NoteId
from aqt.qt import QTimer
from aqt.utils import tooltip

from ..logging_support import logThis
from ..state import (
    CONFIG_IGNORED_KEY,
    LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE,
    LEGACY_ADDON_CUSTOM_DATA_KEY,
    SIBPUSH_IGNORED_KEY,
    SIBPUSH_MARKER_VALUE,
    SIBPUSH_SUSPENDED_KEY,
)
from .query import get_deck_rule, get_deck_rule_by_id

DECK_UNSUSPEND_BATCH_SIZE = 1000
DECK_UNSUSPEND_BATCH_PAUSE_MS = 100
DECK_UNSUSPEND_TOOLTIP_PERIOD_MS = 3000


def _get_variable_chunk_size(batch_size: int) -> int:
    """Return a slightly randomized chunk size around the provided batch size."""

    jitter = max(1, round(batch_size * 0.1))
    lower_bound = max(1, batch_size - jitter)
    upper_bound = batch_size + jitter
    return random.randint(lower_bound, upper_bound)


def _parse_custom_data(card: Card | CardSnapshot) -> dict[str, Any] | None:
    """Parse custom data, returning ``None`` for malformed/non-object payloads."""

    raw_custom_data = getattr(card, "custom_data", "")
    if not raw_custom_data:
        return {}

    try:
        parsed_custom_data = json.loads(raw_custom_data)
    except (TypeError, json.JSONDecodeError):
        return None

    if isinstance(parsed_custom_data, dict):
        return cast(dict[str, Any], parsed_custom_data)

    return None


def _load_custom_data(card: Card | CardSnapshot) -> dict[str, Any]:
    """Return a parsed copy of a card's custom_data payload.

    Malformed and non-object payloads intentionally look empty to marker readers. Mutation
    helpers use ``_parse_custom_data`` directly so they can preserve those payloads unchanged.
    """

    return _parse_custom_data(card) or {}


def _mutate_marker(col: Collection, card: Card, marker_key: str, enabled: bool) -> bool:
    """Set or remove one marker on a freshly fetched card.

    A malformed or non-object non-empty payload is never replaced. This is deliberately a
    conservative failure mode because custom_data may belong partly to another add-on.
    """

    fresh_card = col.get_card(card.id)
    custom_data = _parse_custom_data(fresh_card)
    if custom_data is None:
        logThis(lambda: f"SibPush skipped marker mutation for card {card.id}: invalid custom_data")
        return False

    if enabled:
        if custom_data.get(marker_key) is SIBPUSH_MARKER_VALUE:
            return False
        custom_data[marker_key] = SIBPUSH_MARKER_VALUE
    else:
        if custom_data.get(marker_key) is not SIBPUSH_MARKER_VALUE:
            return False
        custom_data.pop(marker_key, None)

    fresh_card.custom_data = json.dumps(custom_data, ensure_ascii=False) if custom_data else ""
    col.update_card(fresh_card)
    return True


def _card_has_marker(card: Card | CardSnapshot, marker_key: str) -> bool:
    """Return whether a card carries the exact boolean marker value."""

    return _load_custom_data(card).get(marker_key) is SIBPUSH_MARKER_VALUE


def card_is_ignored(card: Card | CardSnapshot) -> bool:
    """Return whether a card is marked as ignored by SibPush."""

    custom_data = _load_custom_data(card)
    return _card_has_marker(card, SIBPUSH_IGNORED_KEY) or (
        custom_data.get(LEGACY_ADDON_CUSTOM_DATA_KEY) == LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE
    )


def card_is_suspended_by_addon(card: Card | CardSnapshot) -> bool:
    """Return whether SibPush owns the card's suspension provenance."""

    return _card_has_marker(card, SIBPUSH_SUSPENDED_KEY)


def set_card_ignored(col: Collection, card: Card) -> None:
    """Mark a card as ignored.

    Ignoring is metadata-only: it leaves the card's queue and any suspension provenance marker
    unchanged. This lets the user temporarily exclude a card without losing the information
    needed to restore it when the ignore marker is later cleared.
    """

    _mutate_marker(col, card, SIBPUSH_IGNORED_KEY, True)


def clear_card_ignored(col: Collection, card: Card) -> None:
    """Remove new and legacy ignored markers while preserving other custom_data keys."""

    _clear_ignored_markers(col, card)


def mark_card_suspended_by_addon(col: Collection, card: Card) -> None:
    """Record that SibPush caused a card suspension."""

    _mutate_marker(col, card, SIBPUSH_SUSPENDED_KEY, True)


def clear_card_suspended_by_addon(col: Collection, card: Card) -> None:
    """Remove only SibPush's suspension provenance marker."""

    _mutate_marker(col, card, SIBPUSH_SUSPENDED_KEY, False)


def _marker_search(marker_key: str) -> str:
    """Return Anki's exact custom-data search expression for a boolean marker."""

    return f"prop:cds:{marker_key}=true"


def get_ignored_card_ids(col: Collection) -> set[CardId]:
    """Return ignored card ids, including legacy data until migration completes."""

    queries = (
        _marker_search(SIBPUSH_IGNORED_KEY),
        f"prop:cds:{LEGACY_ADDON_CUSTOM_DATA_KEY}={LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE}",
    )
    card_ids: set[CardId] = set()
    for query in queries:
        card_ids.update(col.find_cards(query))

    return {
        card_id
        for card_id in card_ids
        if card_is_ignored(col.get_card(card_id))
    }


def _clear_ignored_markers(col: Collection, card: Card) -> bool:
    """Remove current, compatibility, and legacy ignored representations."""

    fresh_card = col.get_card(card.id)
    custom_data = _parse_custom_data(fresh_card)
    if custom_data is None:
        logThis(lambda: f"SibPush skipped ignored-marker clearing for card {card.id}: invalid custom_data")
        return False

    changed = False
    if custom_data.get(SIBPUSH_IGNORED_KEY) is SIBPUSH_MARKER_VALUE:
        custom_data.pop(SIBPUSH_IGNORED_KEY, None)
        changed = True
    if custom_data.get(LEGACY_ADDON_CUSTOM_DATA_KEY) == LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE:
        custom_data.pop(LEGACY_ADDON_CUSTOM_DATA_KEY, None)
        changed = True

    if not changed:
        return False

    fresh_card.custom_data = json.dumps(custom_data, ensure_ascii=False) if custom_data else ""
    col.update_card(fresh_card)
    return True


def clear_all_addon_ignored_markers(col: Collection) -> None:
    """Remove the ignored marker from every card in the collection that carries it.

    Operates collection-wide with no deck or card-type restriction.  Suspend state
    is intentionally left untouched — any follow-on unsuspend logic is the caller's
    responsibility.
    """

    for card_id in get_ignored_card_ids(col):
        _clear_ignored_markers(col, col.get_card(card_id))


def suspend_cards(col: Collection, cards_to_suspend: Sequence[Card], note_id: NoteId) -> None:
    """Suspend a group of cards.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.
        cards_to_suspend (Sequence[anki.cards.Card]): The cards to suspend.
        note_id (int): The note id associated with the cards.

    Returns:
        None: The operation is performed for its side effects.
    """

    cards_to_suspend = [
        card
        for card in cards_to_suspend
        if card.queue != QUEUE_TYPE_SUSPENDED and not card_is_ignored(card)
    ]
    if not cards_to_suspend:
        return

    card_ids = [card.id for card in cards_to_suspend]
    try:
        col.sched.suspend_cards(card_ids)
    except Exception:
        # A batch scheduler exception does not reveal which cards, if any, transitioned. Preserve
        # existing provenance and do not infer ownership from an ambiguous post-state.
        logThis(lambda: f"SibPush could not confirm suspension batch for note {note_id}")
        raise

    # A successful scheduler return confirms that SibPush performed the requested operation. The
    # postcondition limits marker writes to cards that actually ended in the suspended queue.
    for card_id in card_ids:
        fresh_card = col.get_card(card_id)
        if fresh_card.queue == QUEUE_TYPE_SUSPENDED:
            mark_card_suspended_by_addon(col, fresh_card)


def unsuspend_cards(col: Collection, cards_to_unsuspend: Sequence[Card]) -> None:
    """Unsuspend cards and clear provenance only for successful SibPush restorations."""

    card_ids = [
        card.id for card in cards_to_unsuspend if card.queue == QUEUE_TYPE_SUSPENDED
    ]
    if not card_ids:
        return

    try:
        col.sched.unsuspend_cards(card_ids)
    except Exception:
        # A failing batch may have partially transitioned. Its ownership is ambiguous, so leave
        # every provenance marker untouched rather than treating the current queue as proof.
        logThis(lambda: "SibPush could not confirm a card restoration batch")
        raise

    for card_id in card_ids:
        fresh_card = col.get_card(card_id)
        if fresh_card.queue != QUEUE_TYPE_SUSPENDED and card_is_suspended_by_addon(fresh_card):
            clear_card_suspended_by_addon(col, fresh_card)


def note_is_ignored_deck(card: Card) -> bool:
    """Return whether a card belongs to a deck marked as ignored.

    Args:
        card (anki.cards.Card): The card to inspect.

    Returns:
        bool: True when the card's deck is configured to be ignored.
    """

    rule = get_deck_rule(card)
    return bool(rule and rule.get(CONFIG_IGNORED_KEY))


def _card_has_siblings(col: Collection, card: Card) -> bool:
    """Return whether the card's note contains another card for SibPush to manage."""

    return len(col.card_ids_of_note(card.nid)) > 1


def _is_restore_candidate(
    col: Collection,
    card_id: CardId,
    excluded_card_ids: set[CardId] | None = None,
    deck_id: str | None = None,
) -> bool:
    """Re-fetch and validate one card immediately before a restoration."""

    if excluded_card_ids is not None and card_id in excluded_card_ids:
        return False

    card = col.get_card(card_id)
    if deck_id is not None and (
        str(card.did) != str(deck_id)
        or not bool((get_deck_rule_by_id(str(deck_id)) or {}).get(CONFIG_IGNORED_KEY))
    ):
        return False

    return (
        card.queue == QUEUE_TYPE_SUSPENDED
        and card.type == CARD_TYPE_NEW
        and _card_has_siblings(col, card)
        and card_is_suspended_by_addon(card)
        and not card_is_ignored(card)
    )


def _restore_chunk(
    col: Collection,
    candidate_ids: Sequence[CardId],
    excluded_card_ids: set[CardId] | None = None,
    deck_id: str | None = None,
) -> int:
    """Restore one candidate batch and clear provenance only after success."""

    eligible_ids = [
        card_id
        for card_id in candidate_ids
        if _is_restore_candidate(col, card_id, excluded_card_ids, deck_id)
    ]
    if not eligible_ids:
        return 0

    col.sched.unsuspend_cards(eligible_ids)

    restored_count = 0
    for card_id in eligible_ids:
        restored_card = col.get_card(card_id)
        if restored_card.queue == QUEUE_TYPE_SUSPENDED:
            continue

        # The marker must still be present before we remove it. The queue check deliberately
        # accepts any non-suspended post-state because a successful restore may be followed by
        # Anki's normal queue normalization.
        if card_is_suspended_by_addon(restored_card):
            clear_card_suspended_by_addon(col, restored_card)
            restored_count += 1

    return restored_count


def _candidate_restore_ids(
    col: Collection, query: str | Sequence[str], deck_id: str | None = None
) -> list[CardId]:
    """Find broad search candidates and apply authoritative Python validation."""

    queries = (query,) if isinstance(query, str) else query
    candidate_ids: set[CardId] = set()
    for candidate_query in queries:
        candidate_ids.update(col.find_cards(candidate_query))

    return [
        card_id
        for card_id in candidate_ids
        if _is_restore_candidate(col, card_id, deck_id=deck_id)
    ]


def unsuspend_all_addon_cards_in_deck(col: Collection, deck_id: str) -> None:
    """Unsuspend all add-on-managed cards in a specific deck.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.
        deck_id (str): The deck id to scan for suspended cards.

    Returns:
        None: The matching cards are unsuspended for their side effects.
    """

    query = f"did:{deck_id} is:new is:suspended {_marker_search(SIBPUSH_SUSPENDED_KEY)}"
    card_ids_to_unsuspend = _candidate_restore_ids(col, query, deck_id=str(deck_id))

    if not card_ids_to_unsuspend:
        return

    total_count = len(card_ids_to_unsuspend)

    def _show_unsuspend_progress(processed_count: int) -> None:
        tooltip(
            f"SibPush has restored {processed_count:,}/{total_count:,} cards from the ignored deck",
            period=DECK_UNSUSPEND_TOOLTIP_PERIOD_MS,
        )

    def _finish_unsuspending() -> None:
        return

    if total_count <= DECK_UNSUSPEND_BATCH_SIZE:
        restored_count = _restore_chunk(col, card_ids_to_unsuspend, deck_id=str(deck_id))
        _show_unsuspend_progress(restored_count)
        _finish_unsuspending()
        return

    displayed_count = 0

    def _process_chunk(start_index: int = 0) -> None:
        nonlocal displayed_count
        if not bool((get_deck_rule_by_id(str(deck_id)) or {}).get(CONFIG_IGNORED_KEY)):
            _finish_unsuspending()
            return

        chunk_size = _get_variable_chunk_size(DECK_UNSUSPEND_BATCH_SIZE)
        chunk = card_ids_to_unsuspend[start_index : start_index + chunk_size]
        if not chunk:
            _finish_unsuspending()
            return

        _restore_chunk(col, chunk, deck_id=str(deck_id))
        displayed_count = min(total_count, displayed_count + len(chunk))
        _show_unsuspend_progress(displayed_count)

        next_index = start_index + len(chunk)
        if next_index >= total_count:
            _finish_unsuspending()
            return

        cast(Any, QTimer).singleShot(
            DECK_UNSUSPEND_BATCH_PAUSE_MS,
            lambda next_start_index=next_index: _process_chunk(next_start_index),
        )

    _show_unsuspend_progress(0)
    cast(Any, QTimer).singleShot(0, _process_chunk)


def unsuspend_all_addon_cards(
    col: Collection,
    pause_ms: int | None = None,
    on_complete: Callable[[], None] | None = None,
    excluded_card_ids: set[CardId] | None = None,
) -> None:
    """Unsuspend all add-on-managed cards across every deck.

    Args:
        col (anki.collection.Collection): The collection that owns the cards.

    Args:
        pause_ms (int | None): Optional pause between chunks. When omitted, the unsuspend runs
            immediately, preserving the current delete-time behavior.
        on_complete (Callable[[], None] | None): Optional callback that runs after all cards are
            restored.

    Returns:
        None: The matching cards are restored for their side effects.
    """

    query = f"is:new is:suspended {_marker_search(SIBPUSH_SUSPENDED_KEY)}"
    card_ids_to_unsuspend = [
        card_id
        for card_id in _candidate_restore_ids(col, query)
        if excluded_card_ids is None or card_id not in excluded_card_ids
    ]

    if not card_ids_to_unsuspend:
        if on_complete is not None:
            on_complete()
        return

    if pause_ms is None or len(card_ids_to_unsuspend) <= DECK_UNSUSPEND_BATCH_SIZE:
        for start_index in range(0, len(card_ids_to_unsuspend), DECK_UNSUSPEND_BATCH_SIZE):
            chunk = card_ids_to_unsuspend[
                start_index : start_index + DECK_UNSUSPEND_BATCH_SIZE
            ]
            _restore_chunk(col, chunk, excluded_card_ids)

        if on_complete is not None:
            on_complete()
        return

    total_count = len(card_ids_to_unsuspend)
    displayed_count = 0

    def _finish_unsuspending() -> None:
        if on_complete is not None:
            on_complete()

    def _process_chunk(start_index: int = 0) -> None:
        nonlocal displayed_count
        try:
            chunk_size = _get_variable_chunk_size(DECK_UNSUSPEND_BATCH_SIZE)
            chunk = card_ids_to_unsuspend[start_index : start_index + chunk_size]
            if not chunk:
                _finish_unsuspending()
                return

            _restore_chunk(col, chunk, excluded_card_ids)

            displayed_count = min(total_count, displayed_count + len(chunk))

            next_index = start_index + len(chunk)
            if next_index >= total_count:
                _finish_unsuspending()
                return

            cast(Any, QTimer).singleShot(
                pause_ms,
                lambda next_start_index=next_index: _process_chunk(next_start_index),
            )
        except Exception:
            if on_complete is not None:
                on_complete()
            raise

    cast(Any, QTimer).singleShot(0, _process_chunk)
