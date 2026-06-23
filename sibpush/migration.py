"""Versioned startup-migration helpers for the SibPush add-on."""

from __future__ import annotations

from collections.abc import Callable
from anki.collection import Collection

from .logging_support import logThis
from . import state
from .processing.notes import process_all_notes

LEGACY_SUSPENDED_TAG = "SibPush-suspended"
VERSION_2_0_0 = (2, 0, 0)

StartupMigration = Callable[[Collection, Callable[[], None] | None], None]


def migrate_legacy_suspension_tag(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Clear the legacy add-on tag from tagged notes."""
    tagged_note_ids: set[int] = set()

    for card_id in col.find_cards(f"tag:{LEGACY_SUSPENDED_TAG}"):
        card = col.get_card(card_id)
        note = card.note()
        tagged_note_ids.add(note.id)

    if not tagged_note_ids:
        if on_complete is not None:
            on_complete()
        return

    def _finish_migration() -> None:
        col.tags.remove(LEGACY_SUSPENDED_TAG)

        logThis(
            lambda: (
                "SibPush migrated legacy suspension tags on "
                f"{len(tagged_note_ids):,} note(s)"
            )
        )

        if on_complete is not None:
            on_complete()

    _finish_migration()


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

    def _after_legacy_cleanup() -> None:
        process_all_notes(col)
        _finish_version_2_recovery()

    migrate_legacy_suspension_tag(col, on_complete=_after_legacy_cleanup)


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
