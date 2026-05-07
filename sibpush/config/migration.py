"""Legacy configuration migration helpers for the SibPush add-on."""

from __future__ import annotations

from typing import Any

from . import parser
from ..state import get_config_file_path, get_mw


def _get_deck_lookup() -> dict[str, str]:
    """Build a mapping of current deck names to deck ids.

    Returns:
        dict[str, str]: A lookup table keyed by deck name.
    """

    mw = get_mw()
    if mw is None:
        return {}

    col = getattr(mw, "col", None)
    if col is None or not hasattr(col, "decks"):
        return {}

    return {deck.name: str(deck.id) for deck in col.decks.all_names_and_ids()}


def _build_migrated_config(
    config: dict[str, Any], deck_lookup: dict[str, str] | None = None
) -> dict[str, Any] | None:
    """Convert a legacy ignored_decks config into the new schema.

    Args:
        config (dict[str, Any]): The old configuration dictionary.
        deck_lookup (dict[str, str] | None): Optional mapping of deck names to deck ids.

    Returns:
        dict[str, Any] | None: The migrated configuration, or None when migration is not possible.
    """

    legacy_ignored_decks = config.get("ignored_decks")
    if not isinstance(legacy_ignored_decks, list):
        return None

    lookup = deck_lookup or {}
    migrated_rules: list[dict[str, Any]] = []
    default_interval = parser._parse_int(
        config.get("default_interval", config.get("interval", 21)), 21
    )

    for deck_label in legacy_ignored_decks:
        raw_label = str(deck_label).strip()
        if not raw_label:
            continue

        did = lookup.get(raw_label)
        if did is None and raw_label.isdigit():
            # Legacy configs may already have stored the deck id as text; keep that value
            # when there is no current deck-name match to translate it back.
            did = raw_label

        if did is None:
            # We can only migrate a legacy deck name when we know the current deck list.
            if not lookup:
                return None
            continue

        migrated_rules.append({"did": did, "name": raw_label, "ignored": True})

    return {
        "default_interval": default_interval,
        "custom_deck_rules": [{**rule, "interval": default_interval} for rule in migrated_rules],
        "debug": bool(config.get("debug", False)),
    }


def migrate_legacy_config() -> bool:
    """Rewrite an old-style config into the new format when needed.

    Returns:
        bool: True when a migration was written, otherwise False.
    """

    profile_config_file = get_config_file_path()
    if profile_config_file is not None and profile_config_file.exists():
        return False

    addon_manager = parser.addon_manager
    if addon_manager is None:
        return False

    current_config = addon_manager.getConfig(parser._addon_module_name())
    if not isinstance(current_config, dict):
        return False

    if "ignored_decks" in current_config:
        migrated_config = _build_migrated_config(current_config, _get_deck_lookup())
        if migrated_config is None:
            return False

        parser._save_profile_config(migrated_config)
        parser.config_settings.clear()
        parser.config_settings.update(parser.parse_config(migrated_config))
        return True

    parser._save_profile_config(current_config)
    parser.config_settings.clear()
    parser.config_settings.update(parser.parse_config(current_config))
    return True
