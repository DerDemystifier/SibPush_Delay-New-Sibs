"""Main note-processing workflow for the SibPush add-on."""

from __future__ import annotations
from collections.abc import Sequence
from datetime import date

from anki.cards import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED, Card
from anki.collection import Collection
from anki.notes import NoteId

from ..cards.classification import classify_cards
from ..cards.formatting import capture_snapshots, format_note_change
from ..config.parser import config_settings
from ..logging_support import logThis
from ..state import (
    SUSPENDED_BY_ADDON_TAG,
    sync_last_full_scan_date,
    sync_last_unmanaged_note_ids,
)
from .query import (
    get_all_child_cards_batch,
    get_child_cards,
    get_new_note_ids,
    get_note_interval,
    should_run_unmanaged_notes,
)
from .suspension import (
    note_is_ignored_deck,
    remove_suspension_tag_if_no_suspended_cards,
    suspend_cards,
)


def process_note(
    col: Collection,
    note_id: NoteId,
    coming_from_reviewer_hook: bool = False,
    prefetched_siblings: Sequence[Card] | None = None,
) -> None:
    """Process the sibling cards belonging to a single note.

    Args:
        col (anki.collection.Collection): The collection that owns the note.
        note_id (int): The note identifier to process.
        coming_from_reviewer_hook (bool): Whether the call came from the reviewer hook.
        prefetched_siblings (Sequence[Card] | None): Pre-loaded sibling cards from a batch fetch.
            When provided, the database is not queried again for child_card_ids.  Pass `None` (the default) to fall back to the per-note get_child_cards path, which is used by the reviewer hook where only a single note is processed at a time.

    Returns:
        None: The collection is updated in place.
    """

    debug_enabled = bool(config_settings["debug"])

    # Get child cards, either from a previous DB query or by querying the database for the note's child cards.
    siblings = (
        prefetched_siblings if prefetched_siblings is not None else get_child_cards(col, note_id)
    )

    if len(siblings) <= 1:
        # If the note has only one card, then move on.
        return

    # Sort siblings by due date to respect the original order of cards.
    siblings = sorted(siblings, key=lambda card: card.due)

    if coming_from_reviewer_hook and note_is_ignored_deck(siblings[0]):
        # If we're coming from the reviewer hook and the note belongs to an ignored deck, skip.
        # If we're not coming from the reviewer hook, ignored ids are already filtered out by the search query, so we cannot arrive here with an ignored note.
        return

    # for logging purposes, capture the state of the siblings before processing.
    before_snapshots = capture_snapshots(siblings) if debug_enabled else None

    all_new_cards = [card for card in siblings if card.type == CARD_TYPE_NEW]
    note = siblings[0].note()
    interval_threshold = get_note_interval(note, siblings[0])
    new_cards, immature_cards = classify_cards(siblings, interval_threshold)

    # For debugging purposes.
    action_taken: str | None = None
    changed = False

    if immature_cards:
        # Since there are immature cards in the note, suspend all new cards (if not already suspended by the addon).
        new_cards_to_suspend = [card for card in new_cards if card.queue != QUEUE_TYPE_SUSPENDED]

        if not new_cards_to_suspend:
            # If all cards to suspend are already suspended, then this list is empty anyway.
            return

        suspend_cards(col, new_cards_to_suspend, note_id)
        action_taken = f"Suspend {len(new_cards_to_suspend)} new card(s)"
        changed = True
    else:
        # No immature cards, keep the first new card available and suspend the rest.
        if not all_new_cards:
            # If new cards list is empty, then there are no new cards to process anymore, so skip to the next note.
            return

        has_addon_tag = note.has_tag(SUSPENDED_BY_ADDON_TAG)

        # This means that some new cards of this note were previously suspended by the addon.
        # Keep the first available new card active, but heal any later siblings that a user
        # may have manually unsuspended by suspending them again.
        first_new_card = all_new_cards[0]
        if has_addon_tag and first_new_card.queue == QUEUE_TYPE_SUSPENDED:
            col.sched.unsuspend_cards([first_new_card.id])
            changed = True

        new_cards_to_suspend = [
            card for card in all_new_cards[1:] if card.queue != QUEUE_TYPE_SUSPENDED
        ]

        if not has_addon_tag and not new_cards_to_suspend:
            # If the note is not tagged as addon-managed and there are no trailing new cards,
            # then there is nothing to do.
            return

        if coming_from_reviewer_hook:
            # This means we've just seen the card that has just matured, so we should bury the
            # next new card for tomorrow to not review right after.
            col.sched.bury_cards(ids=[first_new_card.id], manual=False)
            changed = True

        if new_cards_to_suspend:
            suspend_cards(col, new_cards_to_suspend, note_id)
            changed = True

        # If the note has the addon tag but there are no new cards left to suspend, then we should remove the stale addon tag.
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
    """Process a batch of notes."""

    if config_settings["debug"]:
        logThis(lambda: f"Processing {len(note_ids)} new note(s)")

    all_siblings_by_nid = get_all_child_cards_batch(col, note_ids)

    for note_id in note_ids:
        process_note(col, note_id, prefetched_siblings=all_siblings_by_nid.get(note_id))


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
