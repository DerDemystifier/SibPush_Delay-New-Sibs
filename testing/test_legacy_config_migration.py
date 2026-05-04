from __future__ import annotations

import importlib

from .addon_utils import load_addon_module


def test_legacy_config_migrates_to_new_schema() -> None:
    """Legacy ignored_decks config should migrate into custom_deck_rules."""

    addon = load_addon_module()
    config_migration = importlib.import_module(f"{addon.__name__}.config_migration")

    migrated = config_migration._build_migrated_config(
        {
            "interval": 21,
            "ignored_decks": ["1777739665453", "Ignored deck"],
            "debug": True,
        },
        {"Ignored deck": "1777739665454"},
    )

    assert migrated == {
        "default_interval": 21,
        "custom_deck_rules": [
            {
                "did": "1777739665453",
                "name": "1777739665453",
                "ignored": True,
                "interval": 21,
            },
            {
                "did": "1777739665454",
                "name": "Ignored deck",
                "ignored": True,
                "interval": 21,
            },
        ],
        "debug": True,
    }


if __name__ == "__main__":
    test_legacy_config_migrates_to_new_schema()
