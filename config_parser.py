import json
from typing import Any, Union
from aqt import mw
from . import log_helper


def parse_config(
    config: Union[dict[str, Any], None]
) -> dict[str, Union[bool, int, list[str]]]:
    """Parse the config object and return the values for debug, interval and ignored_decks.

    Args:
        config (dict[str, object]): The config object to parse.

    Returns:
        tuple: A tuple of three values. The first value is the debug value, the second value is the interval value, the third value is the ignored_decks value.
    """
    debug = bool(config["debug"]) if config is not None else False
    interval = int(config["interval"]) if config is not None else 0
    ignored_decks: list[str] = (
        list(config["ignored_decks"])
        if config is not None and config["ignored_decks"] is not None
        else []
    )

    return {
        "debug": debug,
        "interval": interval,
        "ignored_decks": ignored_decks,
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
                f"interval={config_settings['interval']}, "
                f'ignored_decks={config_settings["ignored_decks"]}'
            )
        )

    # Return the text to be saved to config.json
    return config_text
