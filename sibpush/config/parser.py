"""Configuration parsing and update hooks for the SibPush add-on."""

from __future__ import annotations

import json
from typing import Any, cast

from aqt import mw

from ..logging_support import initialize_log_file, logThis
from ..state import get_mw

ignored_deck_ids: list[str] = []
custom_deck_rules_by_did: dict[str, dict[str, Any]] = {}


def _addon_module_name() -> str:
    """Return the top-level module name used by Anki's add-on manager.

    Returns:
        str: The root package name for this add-on, regardless of internal package depth.
    """

    package_name = __package__ or __name__
    return package_name.split(".", 1)[0]


def _parse_int(value: Any, default: int) -> int:
    """Convert a value to an integer, falling back to a default when needed.

    Args:
        value (Any): The value to convert.
        default (int): The value to return when conversion fails.

    Returns:
        int: The parsed integer or the provided default.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_custom_deck_rule(rule: Any, default_interval: int) -> dict[str, Any] | None:
    """Normalize one custom deck rule into the canonical schema.

    Args:
        rule (Any): The raw rule object from config.json.
        default_interval (int): The interval to use when the rule omits one.

    Returns:
        dict[str, Any] | None: A normalized rule dictionary, or None when the input is invalid.
    """

    if not isinstance(rule, dict):
        return None

    rule_dict = cast(dict[str, object], rule)
    did = str(rule_dict.get("did", "")).strip()
    name = str(rule_dict.get("name", did)).strip() or did

    if not did and not name:
        return None

    return {
        "did": did,
        "name": name,
        "ignored": bool(rule_dict.get("ignored", False)),
        "interval": _parse_int(
            rule_dict.get("interval", default_interval), default_interval
        ),
    }


def _normalize_tag_rule(rule: Any, default_interval: int) -> dict[str, Any] | None:
    """Normalize one tag rule into the canonical schema.

    Args:
        rule (Any): The raw rule object from config.json.
        default_interval (int): The interval to use when the rule omits one.

    Returns:
        dict[str, Any] | None: A normalized rule dictionary, or None when the input is invalid.
    """

    if not isinstance(rule, dict):
        return None

    rule_dict = cast(dict[str, object], rule)
    return {
        "interval": _parse_int(
            rule_dict.get("interval", default_interval), default_interval
        )
    }


def _parse_custom_deck_rules(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract the normalized custom deck rules list from a config object.

    Args:
        config (dict[str, Any] | None): The raw add-on configuration.

    Returns:
        list[dict[str, Any]]: The normalized custom deck rules.
    """

    if config is None:
        return []

    default_interval = _parse_int(config.get("default_interval", 21), 21)
    raw_rules = config.get("custom_deck_rules")
    if isinstance(raw_rules, list):
        typed_rules = cast(list[object], raw_rules)
        return [
            normalized_rule
            for rule in typed_rules
            if (normalized_rule := _normalize_custom_deck_rule(rule, default_interval)) is not None
        ]

    return []


def _extract_ignored_deck_ids(custom_deck_rules: list[dict[str, Any]]) -> list[str]:
    """Extract the deck ids that should be ignored from the normalized rules.

    Args:
        custom_deck_rules (list[dict[str, Any]]): The normalized deck rules.

    Returns:
        list[str]: The deck ids marked as ignored.
    """

    return [
        str(rule.get("did", "")).strip()
        for rule in custom_deck_rules
        if rule.get("ignored") and str(rule.get("did", "")).strip()
    ]


def _index_custom_deck_rules(custom_deck_rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index normalized deck rules by deck id for fast lookup.

    Args:
        custom_deck_rules (list[dict[str, Any]]): The normalized deck rules.

    Returns:
        dict[str, dict[str, Any]]: The rules keyed by deck id.
    """

    return {
        str(rule.get("did", "")).strip(): rule
        for rule in custom_deck_rules
        if str(rule.get("did", "")).strip()
    }


def _get_newly_ignored_deck_ids(
    previous_ignored_deck_ids: list[str], current_ignored_deck_ids: list[str]
) -> list[str]:
    """Return deck ids that were just switched to ignored.

    Args:
        previous_ignored_deck_ids (list[str]): The ignored deck ids before the config save.
        current_ignored_deck_ids (list[str]): The ignored deck ids after the config save.

    Returns:
        list[str]: Deck ids that are now ignored but were not ignored before.
    """

    previous_ids = set(previous_ignored_deck_ids)
    return [
        deck_id
        for deck_id in current_ignored_deck_ids
        if deck_id and deck_id not in previous_ids
    ]


def _unsuspend_cards_for_newly_ignored_decks(previous_ignored_deck_ids: list[str]) -> None:
    """Undo the add-on's suspension for decks that just became ignored."""

    newly_ignored_deck_ids = _get_newly_ignored_deck_ids(
        previous_ignored_deck_ids, ignored_deck_ids
    )
    if not newly_ignored_deck_ids:
        return

    current_mw = get_mw()
    col = getattr(current_mw, "col", None) if current_mw is not None else None
    if col is None:
        return

    from ..processing.suspension import unsuspend_all_addon_cards_in_deck

    for deck_id in newly_ignored_deck_ids:
        unsuspend_all_addon_cards_in_deck(col, deck_id)


def _parse_tag_rules(config: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Extract the normalized tag rules mapping from a config object.

    Args:
        config (dict[str, Any] | None): The raw add-on configuration.

    Returns:
        dict[str, dict[str, Any]]: The normalized tag rules keyed by tag name.
    """

    if config is None:
        return {}

    default_interval = _parse_int(config.get("default_interval", 21), 21)
    raw_rules = config.get("tag_rules")
    if not isinstance(raw_rules, dict):
        return {}

    typed_rules = cast(dict[str, object], raw_rules)
    normalized_rules: dict[str, dict[str, Any]] = {}
    for raw_tag, raw_rule in typed_rules.items():
        tag = str(raw_tag).strip()
        if not tag:
            continue

        normalized_rule = _normalize_tag_rule(raw_rule, default_interval)
        if normalized_rule is None:
            continue

        normalized_rules[tag] = normalized_rule

    return normalized_rules


def parse_config(
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Parse raw configuration data into the cached runtime settings.

    Args:
        config (dict[str, Any] | None): The raw configuration dictionary.

    Returns:
        dict[str, bool | int | list[dict[str, Any]]]: The normalized runtime settings.
    """

    debug = bool(config["debug"]) if config is not None else False
    default_interval = _parse_int(config.get("default_interval", 21), 21) if config is not None else 21
    custom_deck_rules = _parse_custom_deck_rules(config)
    tag_rules = _parse_tag_rules(config)

    custom_deck_rules_by_did.clear()
    custom_deck_rules_by_did.update(_index_custom_deck_rules(custom_deck_rules))
    ignored_deck_ids[:] = _extract_ignored_deck_ids(custom_deck_rules)

    return {
        "debug": debug,
        "default_interval": default_interval,
        "custom_deck_rules": custom_deck_rules,
        "tag_rules": tag_rules,
    }


# Get the config object for your addon.
addon_manager: Any | None = getattr(mw, "addonManager", None) if mw else None
config: dict[str, Any] | None = addon_manager.getConfig(_addon_module_name()) if addon_manager is not None else None
config_settings: dict[str, bool | int | list[dict[str, Any]]] = parse_config(config)


def on_config_save(config_text: str, addon: str) -> str:
    """Handle the config editor save hook and refresh cached settings.

    Args:
        config_text (str): The JSON text that Anki is about to save.
        addon (str): The add-on identifier that triggered the hook.

    Returns:
        str: The configuration text that should be written to disk.
    """

    global config_settings

    if addon != _addon_module_name():
        # If the addon name is not mine, return the text to be saved to config.json.
        return config_text

    # Parse text argument as json.
    config: dict[str, object] = json.loads(config_text)
    previous_ignored_deck_ids = list(ignored_deck_ids)
    debug_before = config_settings["debug"]
    config_settings |= parse_config(config)
    _unsuspend_cards_for_newly_ignored_decks(previous_ignored_deck_ids)

    if config_settings["debug"]:
        if config_settings["debug"] != debug_before:
            # If debug is enabled and it was not enabled before, initialize the log file.
            initialize_log_file()

        logThis(
            lambda: (
                "Config updated: "
                f"debug={config_settings['debug']}, "
                f"default_interval={config_settings['default_interval']}, "
                f'custom_deck_rules={config_settings["custom_deck_rules"]}, '
                f'tag_rules={config_settings["tag_rules"]}, '
                f"ignored_deck_ids={ignored_deck_ids}"
            )
        )

    # Return the text to be saved to config.json.
    return config_text
