"""Main note-processing workflow for the SibPush add-on."""

from __future__ import annotations

from anki.cards import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED
from anki.collection import Collection

from ..cards.classification import classify_cards
from ..cards.formatting import capture_snapshots, format_note_change
from ..config.parser import config_settings
from ..logging_support import logThis
from ..state import SUSPENDED_BY_ADDON_TAG, sync_last_checked_state
from .query import get_child_cards, get_note_interval, should_run_work
from .suspension import note_is_ignored_deck, suspend_cards


def process_note(col: Collection, note_id: int, coming_from_reviewer_hook: bool = False) -> None:
    """Process the sibling cards belonging to a single note.

    Args:
        col (anki.collection.Collection): The collection that owns the note.
        note_id (int): The note identifier to process.
        coming_from_reviewer_hook (bool): Whether the call came from the reviewer hook.

    Returns:
        None: The collection is updated in place.
    """

    debug_enabled = bool(config_settings["debug"])

    siblings = get_child_cards(col, note_id)
    # Sort siblings by due date to respect the original order of cards.
    siblings = sorted(siblings, key=lambda card: card.due)

    if len(siblings) <= 1:
        # If the note has only one card, then move on.
        return

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

        # For logging purposes.
        if has_addon_tag:
            action_taken = "Unsuspend the first new card"
            if coming_from_reviewer_hook:
                action_taken = "Coming from reviewer hook: Unsuspend the first new card, then bury it for tomorrow"
            if new_cards_to_suspend:
                action_taken += f" and suspend {len(new_cards_to_suspend)} trailing new card(s)"
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


def process_all_notes(col: Collection) -> None:
    """Process every eligible new note in the collection.

    Args:
        col (anki.collection.Collection): The collection to process.

    Returns:
        None: The collection is updated in place.
    """

    should_run, current_state = should_run_work(col)
    if not should_run:
        # No need to run the processing again on this render pass.
        return

    new_note_ids = current_state[1]

    if config_settings["debug"]:
        logThis(lambda: f"Processing {len(new_note_ids)} new note(s)")

    for new_note_id in new_note_ids:
        process_note(col, new_note_id)

    sync_last_checked_state(current_state)
