from __future__ import annotations

import json
from importlib import import_module

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..collection_utils import temporary_collection


def _seed_state(state_module: object, col: object, processed: int, synced: int | None) -> None:
    state = state_module
    state.sync_last_processed_mod_ts(processed)
    state.sync_last_sync_mod_ts(synced)
    state.save_persistent_state(col)


def _read_state_file(state_module: object, col: object) -> dict[str, object]:
    state_file = state_module.get_state_file_path(col)
    assert state_file is not None
    return json.loads(state_file.read_text(encoding="utf-8"))


def _read_profile_config_file(state_module: object, col: object) -> dict[str, object]:
    config_file = state_module.get_config_file_path(col)
    assert config_file is not None
    return json.loads(config_file.read_text(encoding="utf-8"))


def test_ignoring_a_deck_keeps_persistent_state() -> None:
    """Ignoring a deck should not invalidate the persistent scan timestamps."""

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
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            active_rule = {
                "did": "1777739665453",
                "name": "Ignore-only deck",
                "ignored": False,
                "interval": 21,
            }
            patched_addon.config_settings["custom_deck_rules"] = [active_rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[active_rule["did"]] = active_rule
            patched_addon.ignored_deck_ids[:] = []

            _seed_state(state_module, col, processed=123, synced=456)

            parser_module.update_custom_deck_rule(active_rule["did"], active_rule["name"], ignored=True)

            assert state_module.get_last_processed_mod_ts() == 123
            assert state_module.get_last_sync_mod_ts() == 456
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [active_rule["did"]],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }
            assert _read_state_file(state_module, col) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
                "pending_browser_work": {
                    "pending_unsuspend_deck_ids": [active_rule["did"]],
                    "pending_processing_state_reset": False,
                    "pending_unmanaged_refresh": False,
                },
            }
            profile_config = _read_profile_config_file(state_module, col)
            assert profile_config["custom_deck_rules"][0]["ignored"] is True


def test_changing_interval_resets_persistent_state() -> None:
    """Changing a deck interval should queue a scan reset without clearing timestamps yet."""

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
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            active_rule = {
                "did": "1777739665453",
                "name": "Interval deck",
                "ignored": False,
                "interval": 21,
            }
            patched_addon.config_settings["custom_deck_rules"] = [active_rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[active_rule["did"]] = active_rule
            patched_addon.ignored_deck_ids[:] = []

            _seed_state(state_module, col, processed=123, synced=456)

            parser_module.update_custom_deck_rule(active_rule["did"], active_rule["name"], interval=33)

            assert state_module.get_last_processed_mod_ts() == 123
            assert state_module.get_last_sync_mod_ts() == 456
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": True,
                "pending_unmanaged_refresh": False,
            }
            assert _read_state_file(state_module, col) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
                "pending_browser_work": {
                    "pending_unsuspend_deck_ids": [],
                    "pending_processing_state_reset": True,
                    "pending_unmanaged_refresh": False,
                },
            }
            profile_config = _read_profile_config_file(state_module, col)
            assert profile_config["custom_deck_rules"][0]["interval"] == 33


def test_changing_tag_rules_resets_persistent_state() -> None:
    """Changing tag rules should queue a scan reset without clearing timestamps yet."""

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
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            _seed_state(state_module, col, processed=123, synced=456)

            config_text = json.dumps(
                {
                    "debug": False,
                    "default_interval": 21,
                    "custom_deck_rules": [],
                    "tag_rules": {"topic": {"interval": 0}},
                }
            )

            parser_module.on_config_save(config_text, addon.__name__)

            assert state_module.get_last_processed_mod_ts() == 123
            assert state_module.get_last_sync_mod_ts() == 456
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": True,
                "pending_unmanaged_refresh": False,
            }
            assert _read_state_file(state_module, col) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
                "pending_browser_work": {
                    "pending_unsuspend_deck_ids": [],
                    "pending_processing_state_reset": True,
                    "pending_unmanaged_refresh": False,
                },
            }
            profile_config = _read_profile_config_file(state_module, col)
            assert profile_config["tag_rules"]["topic"]["interval"] == 0


def test_unignoring_a_deck_resets_persistent_state() -> None:
    """Unignoring a deck should drop stale cleanup work and queue a scan reset."""

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
            parser_module = import_module(f"{addon.__name__}.sibpush.config.parser")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            ignored_rule = {
                "did": "1777739665453",
                "name": "Unignore deck",
                "ignored": True,
                "interval": 21,
            }
            patched_addon.config_settings["custom_deck_rules"] = [ignored_rule]
            patched_addon.custom_deck_rules_by_did.clear()
            patched_addon.custom_deck_rules_by_did[ignored_rule["did"]] = ignored_rule
            patched_addon.ignored_deck_ids[:] = [ignored_rule["did"]]

            state_module.queue_pending_browser_work(deck_ids=[ignored_rule["did"]])
            _seed_state(state_module, col, processed=123, synced=456)

            parser_module.update_custom_deck_rule(
                ignored_rule["did"], ignored_rule["name"], ignored=False, interval=21
            )

            assert state_module.get_last_processed_mod_ts() == 123
            assert state_module.get_last_sync_mod_ts() == 456
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": True,
                "pending_unmanaged_refresh": False,
            }
            assert _read_state_file(state_module, col) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
                "pending_browser_work": {
                    "pending_unsuspend_deck_ids": [],
                    "pending_processing_state_reset": True,
                    "pending_unmanaged_refresh": False,
                },
            }
            profile_config = _read_profile_config_file(state_module, col)
            assert profile_config["custom_deck_rules"][0]["ignored"] is False


if __name__ == "__main__":
    test_ignoring_a_deck_keeps_persistent_state()
    test_changing_tag_rules_resets_persistent_state()
    test_unignoring_a_deck_resets_persistent_state()
