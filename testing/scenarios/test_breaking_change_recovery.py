from __future__ import annotations

import json
from importlib import import_module
from unittest.mock import patch

from anki.consts import QUEUE_TYPE_SUSPENDED

from ..addon_utils import FakeAddonManager, patched_addon_state
from ..card_utils import card_custom_data, card_is_addon_owned, card_queue
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id


def test_needs_breaking_change_recovery_uses_the_version_floor() -> None:
    """The recovery gate should treat versions below the floor as stale."""

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(
            {
                "default_interval": 30,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None

            state_file.write_text(json.dumps({"addon_version": "1.9.9"}), encoding="utf-8")
            state_module.load_persistent_state(col)
            assert state_module.installed_version == "1.9.9"
            assert state_module.needs_breaking_change_recovery() is True

            state_file.write_text(json.dumps({"addon_version": "3.0.0"}), encoding="utf-8")
            state_module.load_persistent_state(col)
            assert state_module.installed_version == "3.0.0"
            assert state_module.needs_breaking_change_recovery() is False


def test_collection_did_load_performs_recovery_when_version_is_missing() -> None:
    """A missing version stamp should trigger the startup recovery flow."""

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(
            {
                "default_interval": 30,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            suspension_module = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            state_file = state_module.get_state_file_path(col)
            config_file = state_module.get_config_file_path(col)

            assert state_file is not None
            assert not state_file.exists()
            assert config_file is not None
            config_file.write_text(
                json.dumps(
                    {
                        "default_interval": 30,
                        "custom_deck_rules": [],
                        "tag_rules": {},
                        "debug": False,
                    }
                ),
                encoding="utf-8",
            )

            model = build_test_notetype(col, card_count=2)
            deck_id = make_test_deck_id(col)
            note, cards = add_note_with_siblings(
                col, model, deck_id, "Recovery test", expected_card_count=2
            )
            suspension_module.suspend_cards(col, [cards[0]], note.id)

            assert card_queue(col, cards[0].id) == QUEUE_TYPE_SUSPENDED
            assert card_is_addon_owned(col, cards[0])

            events: list[str] = []
            real_unsuspend = suspension_module.unsuspend_all_addon_cards
            real_reset = state_module.reset_persistent_state
            real_save = state_module.save_persistent_state

            def fake_unsuspend_all_addon_cards(col_arg: object) -> None:
                events.append("unsuspend")
                real_unsuspend(col_arg)

            def fake_reset_persistent_state(col_arg: object) -> dict[str, object]:
                events.append("reset")
                return real_reset(col_arg)

            def fake_save_persistent_state(col_arg: object) -> dict[str, object]:
                events.append("save")
                return real_save(col_arg)

            with patch.object(
                hooks_module,
                "unsuspend_all_addon_cards",
                side_effect=fake_unsuspend_all_addon_cards,
            ), patch.object(
                hooks_module,
                "reset_persistent_state",
                side_effect=fake_reset_persistent_state,
            ), patch.object(
                hooks_module,
                "save_persistent_state",
                side_effect=fake_save_persistent_state,
            ):
                hooks_module.collection_did_load(col)

            assert events == ["unsuspend", "reset", "save"]
            assert card_queue(col, cards[0].id) != QUEUE_TYPE_SUSPENDED
            assert not card_is_addon_owned(col, cards[0])
            assert card_custom_data(col, cards[0]) == {}
            assert state_module.get_last_processed_mod_ts() == 0
            assert state_module.get_last_sync_mod_ts() is None
            assert state_module.installed_version is None
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "addon_version": state_module.ADDON_VERSION,
            }


def test_collection_did_load_skips_recovery_when_future_version_is_stored() -> None:
    """A newer installed version should not re-run the recovery flow."""

    with temporary_collection() as col:
        fake_manager = FakeAddonManager(
            {
                "default_interval": 30,
                "custom_deck_rules": [],
                "tag_rules": {},
                "debug": False,
            }
        )

        with patched_addon_state(col, addon_manager=fake_manager) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            suspension_module = import_module(f"{addon.__name__}.sibpush.processing.suspension")
            state_file = state_module.get_state_file_path(col)
            config_file = state_module.get_config_file_path(col)

            assert state_file is not None
            assert config_file is not None
            config_file.write_text(
                json.dumps(
                    {
                        "default_interval": 30,
                        "custom_deck_rules": [],
                        "tag_rules": {},
                        "debug": False,
                    }
                ),
                encoding="utf-8",
            )

            model = build_test_notetype(col, card_count=2)
            deck_id = make_test_deck_id(col)
            note, cards = add_note_with_siblings(
                col, model, deck_id, "Future version test", expected_card_count=2
            )
            suspension_module.suspend_cards(col, [cards[0]], note.id)

            state_file.write_text(json.dumps({"addon_version": "3.0.0"}), encoding="utf-8")

            hooks_module.collection_did_load(col)

            assert state_module.installed_version == "3.0.0"
            assert state_module.needs_breaking_change_recovery() is False
            assert card_queue(col, cards[0].id) == QUEUE_TYPE_SUSPENDED
            assert card_is_addon_owned(col, cards[0])
            assert card_custom_data(col, cards[0])["sibpush"] == "suspended"
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "addon_version": state_module.ADDON_VERSION,
            }


if __name__ == "__main__":
    test_needs_breaking_change_recovery_uses_the_version_floor()
    test_collection_did_load_performs_recovery_when_version_is_missing()
    test_collection_did_load_skips_recovery_when_future_version_is_stored()
