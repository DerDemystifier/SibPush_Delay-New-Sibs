import json
from typing import Union
from aqt import mw
from .log_helper import logThis

if not mw:
    raise Exception("SibPush : Anki is not initialized properly")


def parse_config(
    config: Union[dict[str, object], None]
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
config = mw.addonManager.getConfig(__name__)
config_settings = parse_config(config)


def on_config_save(text: str, addon: str) -> None:
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

    logThis("addon_config_editor_will_save_json hook triggered!")

    # Parse text argument as json
    config: dict[str, object] = json.loads(text)
    old_debug = config_settings["debug"]
    config_settings |= parse_config(config)

    if config_settings["debug"] != old_debug:
        logThis("Debug mode is now " + ("enabled" if config_settings["debug"] else "disabled"))

    # Return the text to be saved to config.json
    return text
