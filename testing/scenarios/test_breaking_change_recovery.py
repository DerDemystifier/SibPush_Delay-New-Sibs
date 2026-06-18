from __future__ import annotations

import json
from importlib import import_module
from types import SimpleNamespace
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


def test_browser_render_performs_recovery_when_version_is_missing() -> None:
    """A missing version stamp should defer recovery until browser render."""

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
            migration_module = import_module(f"{addon.__name__}.sibpush.migration")
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
            assert state_module.installed_version is None

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            events: list[str] = []
            scheduled: dict[str, object] = {}

            real_run_startup_migrations = migration_module.run_startup_migrations

            def fake_run_startup_migrations(
                col_arg: object, on_complete: object | None = None
            ) -> None:
                events.append("migrate")
                real_run_startup_migrations(col_arg, on_complete)

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["callback"] = callback

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                events.append(f"scan:{modified_since}")
                assert state_module.installed_version == state_module.ADDON_VERSION
                assert card_queue(col, cards[0].id) != QUEUE_TYPE_SUSPENDED
                assert not card_is_addon_owned(col, cards[0])
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            with patch.object(
                hooks_module, "run_startup_migrations", side_effect=fake_run_startup_migrations
            ), patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert callable(scheduled["callback"])
                assert events == ["migrate"]
                assert card_queue(col, cards[0].id) != QUEUE_TYPE_SUSPENDED
                assert not card_is_addon_owned(col, cards[0])

                scheduled["callback"]()

            assert events == ["migrate", "scan:0"]
            assert state_module.get_last_processed_mod_ts() == 0
            assert state_module.get_last_sync_mod_ts() is None
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "addon_version": state_module.ADDON_VERSION,
            }


def test_browser_render_migrates_legacy_suspension_tags() -> None:
    """Legacy tag cleanup should finish before browser scan processing starts."""

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
            migration_module = import_module(f"{addon.__name__}.sibpush.migration")
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
                col, model, deck_id, "Legacy tag recovery test", expected_card_count=2
            )

            note.add_tag(migration_module.LEGACY_SUSPENDED_TAG)
            col.update_note(note)
            col.sched.suspend_cards([card.id for card in cards])

            assert note.has_tag(migration_module.LEGACY_SUSPENDED_TAG)
            assert card_queue(col, cards[0].id) == QUEUE_TYPE_SUSPENDED
            assert card_queue(col, cards[1].id) == QUEUE_TYPE_SUSPENDED

            state_file.write_text(json.dumps({"addon_version": "1.0.0"}), encoding="utf-8")

            hooks_module.collection_did_load(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            scheduled: dict[str, object] = {}

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["callback"] = callback

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                assert not col.get_note(note.id).has_tag(migration_module.LEGACY_SUSPENDED_TAG)
                assert card_queue(col, cards[0].id) != QUEUE_TYPE_SUSPENDED
                assert card_queue(col, cards[1].id) != QUEUE_TYPE_SUSPENDED
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

            assert "callback" in scheduled
            assert not col.get_note(note.id).has_tag(migration_module.LEGACY_SUSPENDED_TAG)
            assert card_queue(col, cards[0].id) != QUEUE_TYPE_SUSPENDED
            assert card_queue(col, cards[1].id) != QUEUE_TYPE_SUSPENDED
            assert state_module.installed_version == state_module.ADDON_VERSION
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
            assert (
                card_custom_data(col, cards[0])[state_module.ADDON_CUSTOM_DATA_KEY]
                == state_module.ADDON_CUSTOM_DATA_VALUE
            )
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "addon_version": state_module.ADDON_VERSION,
            }


if __name__ == "__main__":
    test_needs_breaking_change_recovery_uses_the_version_floor()
    test_browser_render_performs_recovery_when_version_is_missing()
    test_browser_render_migrates_legacy_suspension_tags()
    test_collection_did_load_skips_recovery_when_future_version_is_stored()
