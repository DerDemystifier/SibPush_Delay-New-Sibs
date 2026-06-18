"""Versioned startup-migration helpers for the SibPush add-on."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any, cast

from anki.cards import CardId
from anki.collection import Collection
from anki.consts import QUEUE_TYPE_SUSPENDED
from aqt.qt import QTimer
from aqt.utils import tooltip

from .logging_support import logThis
from . import state
from .processing.suspension import unsuspend_all_addon_cards

LEGACY_SUSPENDED_TAG = "SibPush-suspended"
LEGACY_UNSUSPEND_BATCH_SIZE = 1000
LEGACY_UNSUSPEND_BATCH_PAUSE_MS = 100
LEGACY_UNSUSPEND_TOOLTIP_PERIOD_MS = 3000
VERSION_2_0_0 = (2, 0, 0)

StartupMigration = Callable[[Collection, Callable[[], None] | None], None]


def _get_variable_chunk_size(batch_size: int) -> int:
    """Return a slightly randomized chunk size around the provided batch size."""

    jitter = max(1, round(batch_size * 0.1))
    lower_bound = max(1, batch_size - jitter)
    upper_bound = batch_size + jitter
    return random.randint(lower_bound, upper_bound)


def migrate_legacy_suspension_tag(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Unsuspend cards and clear the legacy add-on tag from tagged notes.

    This preserves the older version's cleanup behavior during the upgrade to the
    custom-data ownership model.
    """

    card_ids_to_unsuspend: list[CardId] = []
    tagged_note_ids: set[int] = set()

    for card_id in col.find_cards(f"tag:{LEGACY_SUSPENDED_TAG}"):
        card = col.get_card(card_id)
        note = card.note()
        tagged_note_ids.add(note.id)

        if card.queue == QUEUE_TYPE_SUSPENDED:
            card_ids_to_unsuspend.append(card.id)

    if not tagged_note_ids:
        if on_complete is not None:
            on_complete()
        return

    total_count = len(card_ids_to_unsuspend)

    def _show_unsuspend_progress(processed_count: int) -> None:
        try:
            tooltip(
                f"SibPush has restored {processed_count:,}/{total_count:,} cards from the legacy suspended-tag cleanup",
                period=LEGACY_UNSUSPEND_TOOLTIP_PERIOD_MS,
            )
        except AttributeError:
            # Headless test runs may not have an active Qt window yet.
            return

    def _finish_migration() -> None:
        col.tags.remove(LEGACY_SUSPENDED_TAG)

        logThis(
            lambda: (
                "SibPush migrated legacy suspension tags on "
                f"{len(tagged_note_ids):,} note(s) and {total_count:,} card(s)"
            )
        )

        if on_complete is not None:
            on_complete()

    if total_count == 0:
        _finish_migration()
        return

    if total_count <= LEGACY_UNSUSPEND_BATCH_SIZE:
        for card_id in card_ids_to_unsuspend:
            col.sched.unsuspend_cards([card_id])

        _show_unsuspend_progress(total_count)
        _finish_migration()
        return

    displayed_count = 0

    def _process_chunk(start_index: int = 0) -> None:
        nonlocal displayed_count
        try:
            chunk_size = _get_variable_chunk_size(LEGACY_UNSUSPEND_BATCH_SIZE)
            chunk = card_ids_to_unsuspend[start_index : start_index + chunk_size]
            if not chunk:
                _finish_migration()
                return

            col.sched.unsuspend_cards(chunk)
            displayed_count = min(total_count, displayed_count + len(chunk))
            _show_unsuspend_progress(displayed_count)

            next_index = start_index + len(chunk)
            if next_index >= total_count:
                _finish_migration()
                return

            cast(Any, QTimer).singleShot(
                LEGACY_UNSUSPEND_BATCH_PAUSE_MS,
                lambda next_start_index=next_index: _process_chunk(next_start_index),
            )
        except Exception:
            if on_complete is not None:
                on_complete()
            raise

    _show_unsuspend_progress(0)
    cast(Any, QTimer).singleShot(0, _process_chunk)


def migrate_to_version_2(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Apply the version-2 startup recovery pack.

    The pack remains the single place where the v2 upgrade behavior lives so future
    breaking versions can add new packs without changing the hook entry point.
    """

    def _finish_version_2_recovery() -> None:
        state.reset_persistent_state(col)
        state.save_persistent_state(col)
        state.installed_version = state.ADDON_VERSION
        logThis("SibPush performed version-2 recovery on collection load")
        if on_complete is not None:
            on_complete()

    def _run_addon_card_cleanup() -> None:
        unsuspend_all_addon_cards(
            col,
            pause_ms=LEGACY_UNSUSPEND_BATCH_PAUSE_MS,
            on_complete=_finish_version_2_recovery,
        )

    migrate_legacy_suspension_tag(col, on_complete=_run_addon_card_cleanup)


_STARTUP_MIGRATIONS: tuple[tuple[tuple[int, int, int], StartupMigration], ...] = (
    (VERSION_2_0_0, migrate_to_version_2),
)


def _parse_version(value: str | None) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    try:
        parts = [int(part) for part in normalized.split(".")]
    except ValueError:
        return None

    if len(parts) < 3:
        parts.extend([0] * (3 - len(parts)))

    return parts[0], parts[1], parts[2]


def run_startup_migrations(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Run any versioned startup-migration packs needed for this installation."""

    current_version = _parse_version(state.installed_version)

    for target_version, migration in _STARTUP_MIGRATIONS:
        if current_version is None or current_version < target_version:
            migration(col, on_complete)
            return

    if on_complete is not None:
        on_complete()
