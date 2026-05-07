from __future__ import annotations

import json
from importlib import import_module
from types import SimpleNamespace

from unittest.mock import patch

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..collection_utils import temporary_collection
from ..note_utils import make_test_deck_id


class _FakeSignal:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self.callbacks.append(callback)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = _FakeSignal()


class _FakeMenu:
    def __init__(self, title: str | None = None) -> None:
        self.title = title
        self.actions: list[_FakeAction] = []
        self.submenus: list[_FakeMenu] = []

    def addMenu(self, title: str) -> _FakeMenu:
        submenu = _FakeMenu(title)
        self.submenus.append(submenu)
        return submenu

    def addAction(self, text: str) -> _FakeAction:
        action = _FakeAction(text)
        self.actions.append(action)
        return action


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


def test_collection_load_refreshes_menu_state_from_profile_config() -> None:
    """Deck actions should prefer the profile-local config after the collection loads."""

    deck_id = "1777739665453"
    profile_config = {
        "default_interval": 33,
        "custom_deck_rules": [
            {
                "did": deck_id,
                "name": "Profile-local deck",
                "ignored": False,
                "interval": 33,
            }
        ],
        "tag_rules": {"topic": {"interval": 0}},
        "debug": True,
    }
    meta_config = {
        "default_interval": 21,
        "custom_deck_rules": [
            {
                "did": deck_id,
                "name": "Meta deck",
                "ignored": True,
                "interval": 21,
            }
        ],
        "tag_rules": {},
        "debug": False,
    }

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(meta_config)

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            deck_actions = import_module(f"{addon.__name__}.sibpush.ui.deck_actions")
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            config_file = state_module.get_config_file_path(col)

            assert config_file is not None
            config_file.write_text(json.dumps(profile_config), encoding="utf-8")

            parser_module.config_settings.clear()
            parser_module.config_settings.update(parser_module.parse_config(meta_config))

            stale_menu = _FakeMenu("root")
            deck_actions.add_deck_actions_to_options_menu(stale_menu, make_test_deck_id(col))
            assert stale_menu.submenus[0].actions[0].text == "Unignore current deck"

            hooks_module.collection_did_load(col)

            refreshed_menu = _FakeMenu("root")
            deck_actions.add_deck_actions_to_options_menu(refreshed_menu, make_test_deck_id(col))
            assert refreshed_menu.submenus[0].actions[0].text == "Ignore current deck"
            assert json.loads(config_file.read_text(encoding="utf-8")) == profile_config
            assert fake_manager.config == meta_config


def test_collection_load_does_not_fall_back_to_meta_config() -> None:
    """Runtime config should ignore meta.json when the profile-local file is absent."""

    meta_config = {
        "default_interval": 21,
        "custom_deck_rules": [
            {
                "did": "1777739665453",
                "name": "Meta deck",
                "ignored": True,
                "interval": 21,
            }
        ],
        "tag_rules": {},
        "debug": False,
    }

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(meta_config)

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            deck_actions = import_module(f"{addon.__name__}.sibpush.ui.deck_actions")
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            hooks_module.collection_did_load(col)

            assert parser_module.config_settings["custom_deck_rules"] == []

            menu = _FakeMenu("root")
            deck_actions.add_deck_actions_to_options_menu(menu, make_test_deck_id(col))
            assert menu.submenus[0].actions[0].text == "Ignore current deck"
            assert state_module.get_config_file_path(col) is not None
            assert not state_module.get_config_file_path(col).exists()
            assert fake_manager.config == meta_config


def test_collection_load_does_not_queue_a_startup_reset_from_profile_config() -> None:
    """Loading the profile config at startup should not invalidate the saved scan watermark."""

    profile_config = {
        "default_interval": 33,
        "custom_deck_rules": [],
        "tag_rules": {"topic": {"interval": 0}},
        "debug": False,
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
            state_file = state_module.get_state_file_path(col)

            assert config_file is not None
            assert state_file is not None

            config_file.write_text(json.dumps(profile_config), encoding="utf-8")
            state_module.sync_last_processed_mod_ts(123)
            state_module.sync_last_sync_mod_ts(456)
            state_module.save_persistent_state(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            scheduled: dict[str, object] = {}
            captured: dict[str, object] = {}

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["delay_ms"] = delay_ms
                scheduled["callback"] = callback

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                captured["col"] = col_arg
                captured["modified_since"] = modified_since
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ):
                hooks_module.collection_did_load(col)
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert captured["col"] is col
            assert captured["modified_since"] == 123
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
            }
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }


if __name__ == "__main__":
    test_addon_config_editor_displays_profile_config()
    test_addon_config_editor_leaves_other_addons_unchanged()
