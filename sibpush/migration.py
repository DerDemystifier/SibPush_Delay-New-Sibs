"""Versioned startup-migration helpers for the SibPush add-on."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, cast

from anki.collection import Collection
from anki.consts import QUEUE_TYPE_SUSPENDED
from anki.notes import NoteId

from .logging_support import logThis
from . import state
from .processing.notes import process_all_notes
from .processing.suspension import card_is_suspended_by_addon, mark_card_suspended_by_addon

LEGACY_SUSPENDED_TAG = "SibPush-suspended"
VERSION_2_0_0 = (2, 0, 0)
VERSION_2_1_0 = (2, 1, 0)

StartupMigration = Callable[[Collection, Callable[[], None] | None], None]


def migrate_legacy_ignore_markers(col: Collection) -> None:
    """Convert the legacy ``{"sibpush": "ignored"}`` data to the ignore marker.

    The search is intentionally broad and the JSON/value check remains authoritative. Invalid
    or non-object payloads are left byte-for-byte unchanged so startup cannot destroy another
    add-on's custom data.
    """
    migrated_count = 0
    skipped_count = 0
    candidate_ids = col.find_cards(f"has-cd:{state.LEGACY_ADDON_CUSTOM_DATA_KEY}")

    for card_id in candidate_ids:
        card = col.get_card(card_id)
        raw_custom_data = getattr(card, "custom_data", "")
        try:
            parsed: Any = json.loads(raw_custom_data) if raw_custom_data else {}
        except (TypeError, json.JSONDecodeError):
            skipped_count += 1
            continue

        if not isinstance(parsed, dict):
            skipped_count += 1
            continue

        parsed = cast(dict[str, Any], parsed)
        if parsed.get(state.LEGACY_ADDON_CUSTOM_DATA_KEY) == state.LEGACY_ADDON_CUSTOM_DATA_IGNORED_VALUE:
            parsed[state.SIBPUSH_IGNORED_KEY] = state.SIBPUSH_MARKER_VALUE
            parsed.pop(state.LEGACY_ADDON_CUSTOM_DATA_KEY, None)
            card.custom_data = json.dumps(parsed, ensure_ascii=False) if parsed else ""
            col.update_card(card)
            migrated_count += 1

    if migrated_count or skipped_count:
        logThis(
            lambda: (
                "SibPush migrated "
                f"{migrated_count:,} legacy ignored card marker(s)"
                + (f"; skipped {skipped_count:,} invalid payload(s)" if skipped_count else "")
            )
        )


def migrate_legacy_suspension_tag(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Convert legacy suspension tags into card-level suspension provenance.

    Args:
        col (anki.collection.Collection): The collection containing the tagged notes.
        on_complete (Callable[[], None] | None): Optional callback after tag cleanup.

    Returns:
        None: The migration is performed for its side effects.
    """
    tagged_note_ids: set[NoteId] = set()

    for card_id in col.find_cards(f"tag:{LEGACY_SUSPENDED_TAG}"):
        card = col.get_card(card_id)
        note = card.note()
        tagged_note_ids.add(note.id)

    if not tagged_note_ids:
        if on_complete is not None:
            on_complete()
        return

    marked_card_count = 0
    for note_id in tagged_note_ids:
        for card_id in col.card_ids_of_note(note_id):
            card = col.get_card(card_id)
            if card.queue != QUEUE_TYPE_SUSPENDED or card_is_suspended_by_addon(card):
                continue

            mark_card_suspended_by_addon(col, card)
            if card_is_suspended_by_addon(col.get_card(card.id)):
                marked_card_count += 1

    def _finish_migration() -> None:
        col.tags.remove(LEGACY_SUSPENDED_TAG)

        logThis(
            lambda: (
                "SibPush migrated legacy suspension tags on "
                f"{len(tagged_note_ids):,} note(s); marked "
                f"{marked_card_count:,} suspended card(s)"
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
        migrate_legacy_ignore_markers(col)
        process_all_notes(col)
        _finish_version_2_recovery()

    migrate_legacy_suspension_tag(col, on_complete=_after_legacy_cleanup)


def migrate_to_version_2_1(
    col: Collection, on_complete: Callable[[], None] | None = None
) -> None:
    """Migrate the independent card markers for direct upgrades from version 2.0."""

    migrate_legacy_ignore_markers(col)
    state.installed_version = state.ADDON_VERSION
    state.save_persistent_state(col)
    logThis("SibPush migrated legacy card markers to independent provenance markers")
    if on_complete is not None:
        on_complete()


_STARTUP_MIGRATIONS: tuple[tuple[tuple[int, int, int], StartupMigration], ...] = (
    (VERSION_2_0_0, migrate_to_version_2),
    (VERSION_2_1_0, migrate_to_version_2_1),
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
