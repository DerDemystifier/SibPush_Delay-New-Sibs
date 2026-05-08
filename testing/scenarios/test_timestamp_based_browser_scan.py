from __future__ import annotations

import json
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from ..addon_utils import patched_addon_state
from ..collection_utils import temporary_collection


def test_browser_render_uses_the_older_timestamp_watermark() -> None:
    """Browser renders should scan from the older of the processed and sync timestamps."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            state_module.sync_last_processed_mod_ts(300)
            state_module.sync_last_sync_mod_ts(200)
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
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert captured["col"] is col
            assert captured["modified_since"] == 200


def test_browser_render_applies_queued_browser_work_before_scanning() -> None:
    """Queued config work should run before the browser scan starts."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            state_module.sync_last_processed_mod_ts(300)
            state_module.sync_last_sync_mod_ts(200)
            state_module.queue_pending_browser_work(
                deck_ids=["1777739665453"], reset_processing_state=True, refresh_unmanaged_notes=True
            )
            state_module.save_persistent_state(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            scheduled: dict[str, object] = {}
            events: list[str] = []

            real_reset_persistent_state = state_module.reset_persistent_state

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["delay_ms"] = delay_ms
                scheduled["callback"] = callback

            def fake_reset_persistent_state(col_arg: object) -> dict[str, object]:
                events.append("reset")
                return real_reset_persistent_state(col_arg)

            def fake_unsuspend_all_addon_cards_in_deck(col_arg: object, deck_id: str) -> None:
                events.append(f"unsuspend:{deck_id}")

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                events.append(f"scan:{modified_since}")
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            def fake_process_new_unmanaged_notes(col_arg: object) -> None:
                events.append("unmanaged")

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "reset_persistent_state", side_effect=fake_reset_persistent_state
            ), patch.object(
                hooks_module, "unsuspend_all_addon_cards_in_deck", side_effect=fake_unsuspend_all_addon_cards_in_deck
            ), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(
                hooks_module, "process_new_unmanaged_notes", side_effect=fake_process_new_unmanaged_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert events == ["reset", "unsuspend:1777739665453", "scan:0"]
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }


def test_browser_render_runs_unmanaged_refresh_after_partial_scan() -> None:
    """A partial browser scan should still be followed by the unmanaged-note refresh."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            state_module.sync_last_processed_mod_ts(300)
            state_module.sync_last_sync_mod_ts(200)
            state_module.queue_pending_browser_work(refresh_unmanaged_notes=True)
            state_module.save_persistent_state(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            scheduled: dict[str, object] = {}
            events: list[str] = []

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["delay_ms"] = delay_ms
                scheduled["callback"] = callback

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                events.append(f"scan:{modified_since}")
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            def fake_process_new_unmanaged_notes(col_arg: object) -> None:
                events.append("unmanaged")

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(
                hooks_module, "process_new_unmanaged_notes", side_effect=fake_process_new_unmanaged_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert events == ["scan:200", "unmanaged"]
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }


def test_browser_render_clears_stale_sync_watermark_after_scan() -> None:
    """A successful browser scan should consume an older sync watermark instead of reusing it."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None

            state_module.sync_last_processed_mod_ts(300)
            state_module.sync_last_sync_mod_ts(200)
            state_module.save_persistent_state(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            scheduled: dict[str, object] = {}

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["delay_ms"] = delay_ms
                scheduled["callback"] = callback

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                state_module.sync_last_processed_mod_ts(400)
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert state_module.get_last_processed_mod_ts() == 400
            assert state_module.get_last_sync_mod_ts() is None
            assert state_file.read_text(encoding="utf-8") == (
                '{"last_processed_mod_ts":400}'
            )


def test_browser_render_skips_the_immediate_followup_render_after_scan() -> None:
    """A scan should suppress exactly one browser refresh that immediately follows it.

    That follow-up render is usually the browser redrawing after the scan modified the collection.
    Dropping it once keeps the browser from launching a second pass back-to-back.
    """

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")

            state_module.sync_last_processed_mod_ts(400)
            state_module.queue_pending_browser_work(reset_processing_state=True)
            state_module.save_persistent_state(col)

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))
            events: list[str] = []

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                if delay_ms != 2000:
                    raise AssertionError(f"unexpected timer delay: {delay_ms}")

                events.append("schedule-scan")
                events.append("schedule-callback")
                scheduled_callback["callback"] = callback

            scheduled_callback: dict[str, object] = {}

            def fake_process_modified_notes(
                col_arg: object,
                modified_since: int,
                on_complete: object | None = None,
                on_success: object | None = None,
            ) -> None:
                events.append(f"scan:{modified_since}")
                if callable(on_success):
                    on_success()
                if callable(on_complete):
                    on_complete()

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ), patch.object(hooks_module, "show_processing_finished_tooltip"):
                hooks_module.browser_render(browser)

                assert events == ["schedule-scan", "schedule-callback"]
                assert callable(scheduled_callback["callback"])

                scheduled_callback["callback"]()

                assert events == ["schedule-scan", "schedule-callback", "scan:0"]

                hooks_module.browser_render(browser)

                assert events == ["schedule-scan", "schedule-callback", "scan:0"]

                hooks_module.browser_render(browser)

                assert events == ["schedule-scan", "schedule-callback", "scan:0", "schedule-scan", "schedule-callback"]

            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": False,
            }


def test_process_modified_notes_persists_the_processed_watermark() -> None:
    """The browser scan helper should persist the scan-start watermark after it runs."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            notes_module = import_module(f"{addon.__name__}.sibpush.processing.notes")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None

            with patch.object(notes_module.time, "time", return_value=123456), patch.object(
                notes_module, "get_modified_note_ids_since", return_value=[]
            ), patch.object(notes_module, "_process_note_batch") as process_batch:
                notes_module.process_modified_notes(col, 99)

            process_batch.assert_not_called()
            assert state_module.get_last_processed_mod_ts() == 123456
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "last_processed_mod_ts": 123456,
            }


def test_sync_did_finish_persists_the_sync_watermark() -> None:
    """Sync completion should persist the sync watermark for later browser scans."""

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None

            with patch.object(hooks_module.time, "time", return_value=654321), patch.object(
                hooks_module, "process_new_unmanaged_notes"
            ) as process_unmanaged:
                hooks_module.sync_did_finish()

            process_unmanaged.assert_not_called()
            assert state_module.get_last_sync_mod_ts() == 654321
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "last_sync_mod_ts": 654321,
                "pending_browser_work": {
                    "pending_unsuspend_deck_ids": [],
                    "pending_processing_state_reset": False,
                    "pending_unmanaged_refresh": True,
                },
            }


if __name__ == "__main__":
    test_browser_render_uses_the_older_timestamp_watermark()
    test_browser_render_applies_queued_browser_work_before_scanning()
    test_browser_render_runs_unmanaged_refresh_after_partial_scan()
    test_browser_render_clears_stale_sync_watermark_after_scan()
    test_browser_render_skips_the_immediate_followup_render_after_scan()
    test_process_modified_notes_persists_the_processed_watermark()
    test_sync_did_finish_persists_the_sync_watermark()
