from __future__ import annotations

import importlib

from ..addon_utils import load_addon_module


def test_migrates_legacy_config_into_custom_deck_rules() -> None:
    """
    Scenario: Case when an older configuration still stores ignored decks in the legacy schema.

    The migration helper should convert the legacy keys into the new default_interval and
    custom_deck_rules structure without losing the debug setting or the ignored deck mappings.
    """
    addon = load_addon_module()
    config_migration = importlib.import_module(f"{addon.__name__}.sibpush.config.migration")

    print(
        "Before migration, the configuration still uses the legacy ignored_decks list and the old interval key."
    )

    migrated = config_migration._build_migrated_config(
        {
            "interval": 21,
            "ignored_decks": ["1777739665453", "Ignored deck"],
            "debug": True,
        },
        {"Ignored deck": "1777739665454"},
    )

    print(
        "After migration, the config should expose default_interval plus explicit ignored deck rules keyed by deck ID."
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
    test_migrates_legacy_config_into_custom_deck_rules()
