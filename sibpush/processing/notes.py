"""Main note-processing workflow for the SibPush add-on."""

from __future__ import annotations

import time
import random
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, cast

from anki.cards import CARD_TYPE_NEW, QUEUE_TYPE_SIBLING_BURIED, QUEUE_TYPE_SUSPENDED, Card
from anki.collection import Collection
from anki.notes import NoteId
from aqt.qt import QTimer
from aqt.utils import tooltip

from ..cards.classification import classify_cards
from ..cards.formatting import capture_snapshots, format_note_change
from ..config.parser import config_settings
from ..logging_support import logThis
from ..state import (
    SUSPENDED_BY_ADDON_TAG,
    save_persistent_state,
    sync_last_full_scan_date,
    sync_last_processed_mod_ts,
    sync_last_unmanaged_note_ids,
)
from .query import (
    get_all_child_cards_batch,
    get_child_cards,
    get_new_note_ids,
    get_note_interval,
    get_modified_note_ids_since,
    should_run_unmanaged_notes,
)
from .suspension import (
    note_is_ignored_deck,
    remove_suspension_tag_if_no_suspended_cards,
    suspend_cards,
)

MODIFIED_NOTE_BATCH_SIZE = 1000
MODIFIED_NOTE_BATCH_PAUSE_MS = 100
MODIFIED_NOTE_TOOLTIP_PERIOD_MS = 3000
PROCESSING_FINISHED_TOOLTIP_PERIOD_MS = 2000


def _get_variable_chunk_size(batch_size: int) -> int:
    """Return a slightly randomized chunk size around the provided batch size."""

    jitter = max(1, round(batch_size * 0.1))
    lower_bound = max(1, batch_size - jitter)
    upper_bound = batch_size + jitter
    return random.randint(lower_bound, upper_bound)


def process_note(
    col: Collection,
    note_id: NoteId,
    coming_from_reviewer_hook: bool = False,
    prefetched_siblings: Sequence[Card] | None = None,
) -> None:
    """Process the sibling cards belonging to a single note.

    This is the heart of SibPush. It implements the core logic:

    1. If there are immature cards (interval < threshold), suspend all new cards
    2. If all cards are mature, unsuspend the first new card and suspend the rest
    3. If coming from the reviewer (user just answered a card), bury the next new card
       for tomorrow to avoid showing it immediately after its sibling matured

    The algorithm ensures proper spacing between sibling cards by:
    - Keeping new siblings suspended while any sibling is still immature
    - Only introducing one new sibling at a time (first card stays active, rest suspended)
    - Preventing immediate review by burying when coming from reviewer hook

    Args:
        col (anki.collection.Collection): The collection that owns the note.
        note_id (int): The note identifier to process.
        coming_from_reviewer_hook (bool): Whether the call came from the reviewer hook.
            When True, indicates the user just answered a card, so we bury the next new
            card to prevent immediate review.
        prefetched_siblings (Sequence[Card] | None): Pre-loaded sibling cards from a batch fetch.
            When provided, skips the per-note database query. Used by batch processing to
            avoid N database calls. Pass None (default) to query the database for this note's cards.

    Returns:
        None: The collection is updated in place with suspended/unsuspended cards and tags.
    """

    debug_enabled = bool(config_settings["debug"])

    # STEP 1: Get the sibling cards for this note
    # Either use prefetched cards from a batch query, or query the database for this note
    siblings = (
        prefetched_siblings if prefetched_siblings is not None else get_child_cards(col, note_id)
    )

    # Early exit: Single-card notes don't have siblings to manage
    if len(siblings) <= 1:
        return

    # Sort siblings by due date to maintain Anki's original card order
    # This ensures we process cards in the sequence the user expects
    siblings = sorted(siblings, key=lambda card: card.due)

    # STEP 2: Check if this deck is configured to be ignored
    # Ignored decks skip all SibPush processing
    if coming_from_reviewer_hook and note_is_ignored_deck(siblings[0]):
        # When coming from reviewer hook, we need to check manually since ignored
        # decks aren't filtered out of the reviewer workflow
        # (Browser-driven scans already exclude ignored decks in the search query)
        return

    # STEP 3: Capture state before processing (for debug logging)
    before_snapshots = capture_snapshots(siblings) if debug_enabled else None

    all_new_cards = [card for card in siblings if card.type == CARD_TYPE_NEW]
    note = siblings[0].note()

    # STEP 4: Determine the maturity threshold for this note
    # Check tag rules first, then deck rules, then fall back to default interval
    interval_threshold = get_note_interval(note, siblings[0])

    # STEP 5: Classify siblings into new cards and immature cards
    # Immature = reviewed but interval < threshold (still learning)
    # New = never reviewed yet (candidates for suspension)
    new_cards, immature_cards = classify_cards(siblings, interval_threshold)

    # Variables for tracking actions taken (used in debug logging)
    action_taken: str | None = None
    changed = False

    # DECISION TREE: Two main branches based on whether immature cards exist

    if immature_cards:
        # BRANCH A: There are immature siblings - suspend ALL new cards
        # This prevents learning new siblings while old ones are still maturing
        new_cards_to_suspend = [card for card in new_cards if card.queue != QUEUE_TYPE_SUSPENDED]

        if not new_cards_to_suspend:
            # All new cards are already suspended - nothing to do
            return

        # Suspend the new cards and tag the note as addon-managed
        suspend_cards(col, new_cards_to_suspend, note_id)
        action_taken = f"Suspend {len(new_cards_to_suspend)} new card(s)"
        changed = True
    else:
        # BRANCH B: No immature cards - all siblings are either new or mature
        # Strategy: Keep first new card active, suspend the rest, unsuspend if needed

        if not all_new_cards:
            # No new cards left to process - all cards are mature or learning
            return

        has_addon_tag = note.has_tag(SUSPENDED_BY_ADDON_TAG)

        # SUB-BRANCH B1: Note was previously managed by addon (has suspension tag)
        # This means some siblings were suspended earlier and may now be ready
        first_new_card = all_new_cards[0]

        if has_addon_tag and first_new_card.queue == QUEUE_TYPE_SUSPENDED:
            # The first new card is suspended - unsuspend it to make it available
            col.sched.unsuspend_cards([first_new_card.id])
            changed = True

        # Get the trailing new cards (2nd, 3rd, etc.) that should stay suspended
        new_cards_to_suspend = [
            card for card in all_new_cards[1:] if card.queue != QUEUE_TYPE_SUSPENDED
        ]

        # SUB-BRANCH B2: Note not tagged and no trailing cards to suspend
        # Nothing to do - this is a fresh note or already properly managed
        if not has_addon_tag and not new_cards_to_suspend:
            return

        # SUB-BRANCH B3: Coming from reviewer hook - special handling
        # The user just reviewed a card, so bury the next new card for tomorrow
        # to prevent immediate review of siblings
        if coming_from_reviewer_hook and first_new_card.queue != QUEUE_TYPE_SIBLING_BURIED:
            # Bury the first new card until tomorrow (auto-unbury).
            # Skip the write if Anki already left the card buried for the day.
            col.sched.bury_cards(ids=[first_new_card.id], manual=False)
            changed = True

        # Suspend any trailing new cards that aren't already suspended
        if new_cards_to_suspend:
            suspend_cards(col, new_cards_to_suspend, note_id)
            changed = True

        # CLEANUP: Remove the addon tag if there are no suspended cards left
        # This happens when all new siblings have been introduced
        tag_removed = False
        if not new_cards_to_suspend and has_addon_tag:
            tag_removed = remove_suspension_tag_if_no_suspended_cards(col, note, note.cards())
            changed = changed or tag_removed

        # For logging purposes.
        if has_addon_tag:
            action_taken = "Unsuspend the first new card"
            if coming_from_reviewer_hook:
                action_taken = "Coming from reviewer hook: Unsuspend the first new card, then bury it for tomorrow"
            if new_cards_to_suspend:
                action_taken += f" and suspend {len(new_cards_to_suspend)} trailing new card(s)"
            elif tag_removed:
                action_taken += " and remove the stale suspension tag"
        elif coming_from_reviewer_hook:
            action_taken = f"Coming from reviewer hook: bury the first new card for tomorrow and suspend {len(new_cards_to_suspend)} trailing new card(s)"
        else:
            action_taken = f"Suspend {len(new_cards_to_suspend)} trailing new card(s)"

    if debug_enabled and changed and action_taken:
        updated_siblings = sorted(get_child_cards(col, note_id), key=lambda card: card.due)
        after_snapshots = capture_snapshots(updated_siblings)
        logThis(
            lambda: format_note_change(
                note,
                col,
                note_id,
                before_snapshots or [],
                after_snapshots,
                action_taken,
            )
        )


def _process_note_batch(col: Collection, note_ids: Sequence[NoteId]) -> None:
    """Process a batch of notes efficiently with a single database query.

    This is a performance optimization that processes multiple notes at once.
    Instead of making N database queries (one per note), it:
    1. Fetches all sibling cards for all notes in a single query
    2. Processes each note with its prefetched siblings

    This dramatically reduces database overhead during full scans.

    Args:
        col (anki.collection.Collection): The collection to process.
        note_ids (Sequence[anki.notes.NoteId]): The note ids to process in this batch.

    Returns:
        None: Each note is processed in place via process_note().
    """

    if config_settings["debug"]:
        logThis(lambda: f"Processing {len(note_ids)} note(s)")

    # Batch fetch all sibling cards for all notes in one database query
    # Returns: {note_id: [card1, card2, ...], ...}
    all_siblings_by_nid = get_all_child_cards_batch(col, note_ids)

    # Process each note with its prefetched siblings
    for note_id in note_ids:
        process_note(col, note_id, prefetched_siblings=all_siblings_by_nid.get(note_id))


def _persist_processed_mod_timestamp(col: Collection, scan_started_at: int) -> None:
    """Persist the processed watermark after a browser scan completes."""

    sync_last_processed_mod_ts(scan_started_at)
    save_persistent_state(col)


def _show_modified_note_progress(processed_count: int, total_count: int) -> None:
    """Show a short tooltip describing modified-note scan progress."""

    tooltip(
        f"SibPush has processed {processed_count:,}/{total_count:,} notes",
        period=MODIFIED_NOTE_TOOLTIP_PERIOD_MS,
    )


def show_processing_finished_tooltip() -> None:
    """Show a short tooltip when the browser batch has finished."""

    tooltip(
        "SibPush has finished processing",
        period=PROCESSING_FINISHED_TOOLTIP_PERIOD_MS,
    )


def _run_modified_note_chunked_scan(
    col: Collection,
    modified_note_ids: Sequence[NoteId],
    scan_started_at: int,
    on_complete: Callable[[], None] | None = None,
    on_success: Callable[[], None] | None = None,
) -> None:
    """Process modified note ids in chunks and pause briefly between batches.

    The scan is intentionally chunked so large browser refreshes keep the UI responsive. The
    watermark is persisted only after the entire scan completes, so a partial run does not skip
    any remaining modified notes on the next browser refresh.
    """

    note_ids = list(modified_note_ids)
    if not note_ids:
        _persist_processed_mod_timestamp(col, scan_started_at)
        if on_complete is not None:
            on_complete()
        return

    total_count = len(note_ids)
    displayed_count = 0

    def _finish_scan() -> None:
        _show_modified_note_progress(total_count, total_count)
        _persist_processed_mod_timestamp(col, scan_started_at)
        show_processing_finished_tooltip()
        try:
            if on_success is not None:
                on_success()
        finally:
            if on_complete is not None:
                on_complete()

    def _process_chunk(start_index: int = 0) -> None:
        nonlocal displayed_count
        try:
            chunk_size = _get_variable_chunk_size(MODIFIED_NOTE_BATCH_SIZE)
            chunk = note_ids[start_index : start_index + chunk_size]
            if not chunk:
                _finish_scan()
                return

            _process_note_batch(col, chunk)
            displayed_count = min(total_count, displayed_count + len(chunk))
            _show_modified_note_progress(displayed_count, total_count)

            next_index = start_index + len(chunk)
            if next_index >= len(note_ids):
                _finish_scan()
                return

            cast(Any, QTimer).singleShot(
                MODIFIED_NOTE_BATCH_PAUSE_MS,
                lambda next_start_index=next_index: _process_chunk(next_start_index),
            )
        except Exception:
            if on_complete is not None:
                on_complete()
            raise

    cast(Any, QTimer).singleShot(0, _process_chunk)


def process_all_notes(col: Collection) -> None:
    """Process every eligible new note in the collection.

    Args:
        col (anki.collection.Collection): The collection to process.

    Returns:
        None: The collection is updated in place.
    """

    current_full_scan_date = date.today().isoformat()
    new_note_ids = get_new_note_ids(col)

    _process_note_batch(col, new_note_ids)
    sync_last_full_scan_date(current_full_scan_date)


def process_modified_notes(
    col: Collection,
    modified_since: int,
    on_complete: Callable[[], None] | None = None,
    on_success: Callable[[], None] | None = None,
) -> None:
    """Process notes changed after a timestamp and persist the new scan watermark.

    The browser path uses this helper instead of a day-gated scan. The watermark is recorded at
    the end of the scan so we do not skip notes that were still waiting in later chunks when a
    browser scan began.

    Args:
        col (anki.collection.Collection): The collection to process.
        modified_since (int): The timestamp threshold for changed notes.
        on_complete (Callable[[], None] | None): Cleanup callback that always runs when the scan
            finishes or errors.
        on_success (Callable[[], None] | None): Optional callback that runs only after a
            successful scan.

    Returns:
        None: The collection is updated in place.
    """

    current_scan_timestamp = int(time.time())
    modified_note_ids = get_modified_note_ids_since(col, modified_since)

    if modified_note_ids and len(modified_note_ids) <= MODIFIED_NOTE_BATCH_SIZE:
        if modified_note_ids:
            # Avoid calling _process_note_batch with an empty list
            _process_note_batch(col, modified_note_ids)

        _persist_processed_mod_timestamp(col, current_scan_timestamp)
        try:
            if on_success is not None:
                on_success()
        finally:
            if on_complete is not None:
                on_complete()
        return

    _run_modified_note_chunked_scan(
        col,
        modified_note_ids,
        current_scan_timestamp,
        on_complete,
        on_success,
    )


def process_new_unmanaged_notes(col: Collection) -> None:
    """Process only unmanaged new notes in the collection.

    This is the lighter recurring scan used after the initial startup/day-change full pass.
    It only revisits notes that are still new and do not already have the add-on tag.

    Args:
        col (anki.collection.Collection): The collection to process.

    Returns:
        None: The collection is updated in place.
    """

    should_run, current_unmanaged_note_ids = should_run_unmanaged_notes(col)
    if not should_run:
        return

    _process_note_batch(col, current_unmanaged_note_ids)
    sync_last_unmanaged_note_ids(current_unmanaged_note_ids)
