from __future__ import annotations

import json
from importlib import import_module

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..collection_utils import temporary_collection


def test_addon_config_editor_displays_profile_config() -> None:
    """The Add-ons Config panel should display the profile-local config when it exists."""

    profile_config = {
        "default_interval": 33,
        "custom_deck_rules": [
            {
                "did": "1777739665453",
                "name": "Profile-local deck",
                "ignored": True,
                "interval": 33,
            }
        ],
        "tag_rules": {"topic": {"interval": 0}},
        "debug": True,
    }

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(
            {
                "default_interval": 21,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            config_file = state_module.get_config_file_path(col)

            assert config_file is not None
            config_file.write_text(json.dumps(profile_config), encoding="utf-8")

            displayed_text = hooks_module.addon_config_editor_will_display_json(
                json.dumps(fake_manager.config)
            )

            assert json.loads(displayed_text) == profile_config
            assert fake_manager.config == {
                "default_interval": 21,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }


def test_addon_config_editor_leaves_other_addons_unchanged() -> None:
    """Unrelated add-on configs should pass through the display hook unchanged."""

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(
            {
                "default_interval": 21,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")

            other_config_text = json.dumps({"theme": "dark", "enabled": True})

            assert hooks_module.addon_config_editor_will_display_json(other_config_text) == other_config_text


if __name__ == "__main__":
    test_addon_config_editor_displays_profile_config()
    test_addon_config_editor_leaves_other_addons_unchanged()
