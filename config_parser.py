import json
from typing import Any, Union, cast
from aqt import mw
from . import log_helper

ignored_deck_ids: list[str] = []
custom_deck_rules_by_did: dict[str, dict[str, Any]] = {}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_custom_deck_rule(rule: Any, default_interval: int) -> dict[str, Any] | None:
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
        "interval": _parse_int(rule_dict.get("interval", default_interval), default_interval),
    }


def _parse_custom_deck_rules(config: dict[str, Any] | None) -> list[dict[str, Any]]:
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
    return [
        str(rule.get("did", "")).strip()
        for rule in custom_deck_rules
        if rule.get("ignored") and str(rule.get("did", "")).strip()
    ]


def _index_custom_deck_rules(custom_deck_rules: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(rule.get("did", "")).strip(): rule
        for rule in custom_deck_rules
        if str(rule.get("did", "")).strip()
    }


def parse_config(
    config: Union[dict[str, Any], None],
) -> dict[str, Union[bool, int, list[dict[str, Any]]]]:
    """Parse the config object and return the values for debug, default_interval and custom_deck_rules.

    Args:
        config (dict[str, object]): The config object to parse.

    Returns:
        dict: A dictionary containing debug, default_interval and custom_deck_rules.
    """
    debug = bool(config["debug"]) if config is not None else False
    default_interval = (
        _parse_int(config.get("default_interval", 21), 21) if config is not None else 21
    )
    custom_deck_rules = _parse_custom_deck_rules(config)

    custom_deck_rules_by_did.clear()
    custom_deck_rules_by_did.update(_index_custom_deck_rules(custom_deck_rules))
    ignored_deck_ids[:] = _extract_ignored_deck_ids(custom_deck_rules)

    return {
        "debug": debug,
        "default_interval": default_interval,
        "custom_deck_rules": custom_deck_rules,
    }


# Get the config object for your addon
addon_manager = getattr(mw, "addonManager", None) if mw else None
config = addon_manager.getConfig(__name__) if addon_manager is not None else None
config_settings = parse_config(config)


def on_config_save(config_text: str, addon: str) -> str:
    """
    This function is triggered when the addon_config_editor_will_save_json hook is called.
    It parses the text argument as json, updates the global config_settings dictionary with the parsed config,
    and returns the text to be saved to config.json.

    Args:
        text (str): The text to be parsed as json.
        addon (str): The name of the addon.

    Returns:
        str: The text to be saved to config.json.
    """

    global config_settings

    if addon != "SibPush_Delay-New-Sibs":
        # If the addon name is not mine, return the text to be saved to config.json
        return config_text

    # Parse text argument as json
    config: dict[str, object] = json.loads(config_text)
    debug_before = config_settings["debug"]
    config_settings |= parse_config(config)

    if config_settings["debug"]:
        if config_settings["debug"] != debug_before:
            # If debug is enabled and it was not enabled before, initialize the log file
            log_helper.initialize_log_file()

        log_helper.logThis(
            lambda: (
                "Config updated: "
                f"debug={config_settings['debug']}, "
                f"default_interval={config_settings['default_interval']}, "
                f'custom_deck_rules={config_settings["custom_deck_rules"]}, '
                f"ignored_deck_ids={ignored_deck_ids}"
            )
        )

    # Return the text to be saved to config.json
    return config_text
