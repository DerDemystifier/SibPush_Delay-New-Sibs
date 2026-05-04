"""Temporary legacy config migration helpers.

Delete this module after the migration window ends.
"""

from __future__ import annotations

from typing import Any

from aqt import mw

from . import config_parser


def _get_deck_lookup() -> dict[str, str]:
    if mw is None:
        return {}

    col = getattr(mw, "col", None)
    if col is None or not hasattr(col, "decks"):
        return {}

    return {deck.name: str(deck.id) for deck in col.decks.all_names_and_ids()}


def _build_migrated_config(
    config: dict[str, Any], deck_lookup: dict[str, str] | None = None
) -> dict[str, Any] | None:
    legacy_ignored_decks = config.get("ignored_decks")
    if not isinstance(legacy_ignored_decks, list):
        return None

    lookup = deck_lookup or {}
    migrated_rules: list[dict[str, Any]] = []
    default_interval = config_parser._parse_int(
        config.get("default_interval", config.get("interval", 21)), 21
    )

    for deck_label in legacy_ignored_decks:
        raw_label = str(deck_label).strip()
        if not raw_label:
            continue

        did = lookup.get(raw_label)
        if did is None and raw_label.isdigit():
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
    """Rewrite an old-style config into the new format, if needed.

    TODO: delete this startup hook after the migration window closes.
    """

    if config_parser.addon_manager is None:
        return False

    current_config = config_parser.addon_manager.getConfig(config_parser.__name__)
    if not isinstance(current_config, dict) or "ignored_decks" not in current_config:
        return False

    migrated_config = _build_migrated_config(current_config, _get_deck_lookup())
    if migrated_config is None:
        return False

    write_config = getattr(config_parser.addon_manager, "writeConfig", None) or getattr(
        config_parser.addon_manager, "setConfig", None
    )
    if write_config is None:
        raise AttributeError("Anki add-on manager does not provide a config write method")

    try:
        write_config(config_parser.__name__, migrated_config)
    except TypeError:
        write_config(migrated_config)

    config_parser.config_settings.clear()
    config_parser.config_settings.update(config_parser.parse_config(migrated_config))
    return True
