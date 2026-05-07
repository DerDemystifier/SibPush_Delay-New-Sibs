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
            ) -> None:
                captured["col"] = col_arg
                captured["modified_since"] = modified_since
                if callable(on_complete):
                    on_complete()

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot), patch.object(
                hooks_module, "process_modified_notes", side_effect=fake_process_modified_notes
            ):
                hooks_module.browser_render(browser)

                assert scheduled["delay_ms"] == 2000
                assert callable(scheduled["callback"])

                scheduled["callback"]()

            assert captured["col"] is col
            assert captured["modified_since"] == 200


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

            process_unmanaged.assert_called_once_with(col)
            assert state_module.get_last_sync_mod_ts() == 654321
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "last_sync_mod_ts": 654321,
            }


if __name__ == "__main__":
    test_browser_render_uses_the_older_timestamp_watermark()
    test_process_modified_notes_persists_the_processed_watermark()
    test_sync_did_finish_persists_the_sync_watermark()
