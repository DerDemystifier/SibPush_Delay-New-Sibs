from __future__ import annotations

import json
from importlib import import_module

from ..addon_utils import patched_addon_state
from ..collection_utils import temporary_collection


def test_state_file_round_trips_and_reset_clears_memory() -> None:
    """
    Scenario: The add-on persists timestamp state to a per-collection state.json file.

    The file should load cleanly when it does not exist yet, round-trip values after saving,
    and clear both the file contents and the in-memory caches when reset is called.
    """

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            state_module = import_module(f"{patched_addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None
            assert not state_file.exists()

            loaded_state = state_module.load_persistent_state(col)
            assert loaded_state == {"last_processed_mod_ts": 0, "last_sync_mod_ts": None}
            assert state_module.get_last_processed_mod_ts() == 0
            assert state_module.get_last_sync_mod_ts() is None

            state_module.sync_last_processed_mod_ts(123)
            state_module.sync_last_sync_mod_ts(456)
            saved_state = state_module.save_persistent_state(col)

            assert saved_state == {"last_processed_mod_ts": 123, "last_sync_mod_ts": 456}
            assert state_file.exists()
            assert json.loads(state_file.read_text(encoding="utf-8")) == {
                "last_processed_mod_ts": 123,
                "last_sync_mod_ts": 456,
            }

            state_module.sync_last_processed_mod_ts(999)
            state_module.sync_last_sync_mod_ts(111)
            state_module.sync_last_full_scan_date("2026-05-07")
            state_module.sync_last_unmanaged_note_ids([1, 2, 3])

            reset_state = state_module.reset_persistent_state(col)

            assert reset_state == {"last_processed_mod_ts": 0, "last_sync_mod_ts": None}
            assert json.loads(state_file.read_text(encoding="utf-8")) == {}
            assert state_module.get_last_processed_mod_ts() == 0
            assert state_module.get_last_sync_mod_ts() is None
            assert state_module.get_last_full_scan_date() is None
            assert state_module.get_last_unmanaged_note_ids() is None


if __name__ == "__main__":
    test_state_file_round_trips_and_reset_clears_memory()
