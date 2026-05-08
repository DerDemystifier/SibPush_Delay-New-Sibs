from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from anki.consts import QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED

from ..addon_utils import patched_addon_state
from ..card_utils import assert_card_queues
from ..collection_utils import temporary_collection
from ..note_utils import add_note_with_siblings, build_test_notetype, make_test_deck_id
from ..print_utils import print_collection_state


def test_browser_render_delays_the_initial_full_scan() -> None:
    """
    Scenario: Case when the deck browser renders for the first time after startup.

    The add-on should schedule the initial full scan instead of running it immediately so the
    browser can finish loading first.
    """

    with temporary_collection() as col:
        addon = None
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)
        note, cards = add_note_with_siblings(col, model, deck_id, "Delayed startup note")

        print("Before the first browser render, the note is still completely fresh.")
        print_collection_state(col, "Before delayed browser render")

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")

            scheduled: dict[str, object] = {}

            def fake_single_shot(delay_ms: int, callback: object) -> None:
                scheduled["delay_ms"] = delay_ms
                scheduled["callback"] = callback

            browser = SimpleNamespace(mw=SimpleNamespace(col=col))

            with patch.object(hooks_module.QTimer, "singleShot", side_effect=fake_single_shot):
                hooks_module.browser_render(browser)

            assert scheduled["delay_ms"] == 2000
            assert callable(scheduled["callback"])
            assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG) is False

            print("After the browser render, the full scan is still pending because it was deferred.")
            print_collection_state(col, "After browser render before delayed scan runs")

            scheduled["callback"]()

        print("After the delayed scan runs, the note is processed normally.")
        print_collection_state(col, "After delayed browser scan")

        assert_card_queues(col, cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED])
        assert col.get_note(note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


def test_sync_finish_processes_only_unmanaged_new_notes() -> None:
    """
    Scenario: Case when a sync finishes after the add-on already processed the collection once.

    The sync hook should queue unmanaged-note refresh work for the next browser render instead of
    processing notes immediately.
    """

    with temporary_collection() as col:
        model = build_test_notetype(col)
        deck_id = make_test_deck_id(col)

        managed_note, managed_cards = add_note_with_siblings(col, model, deck_id, "Managed note")
        new_note, new_cards = add_note_with_siblings(col, model, deck_id, "Synced unmanaged note")

        print("Before the initial processing pass, both notes are still fresh.")
        print_collection_state(col, "Before initial full scan")

        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            browser = SimpleNamespace(mw=SimpleNamespace(col=col))

            patched_addon.process_all_notes(col)

            print("After the initial full scan, the managed note has been tagged and partially suspended.")
            print_collection_state(col, "After initial full scan")

            assert_card_queues(
                col, managed_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert col.get_note(managed_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)

            assert_card_queues(
                col, new_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert col.get_note(new_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)

            hooks_module.sync_did_finish()

            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": False,
                "pending_unmanaged_refresh": True,
            }

            assert_card_queues(
                col, managed_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert col.get_note(managed_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
            assert_card_queues(
                col, new_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
            )
            assert col.get_note(new_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)

            hooks_module.browser_render(browser)

        print("After sync finishes, only the newly introduced unmanaged note should be processed.")
        print_collection_state(col, "After sync unmanaged refresh")

        assert_card_queues(
            col, managed_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(managed_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)
        assert_card_queues(
            col, new_cards, [QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_SUSPENDED]
        )
        assert col.get_note(new_note.id).has_tag(addon.SUSPENDED_BY_ADDON_TAG)


def test_collection_will_temporarily_close_queues_a_full_reset() -> None:
    """Temporary collection closure should queue a full browser reprocessing pass.

    One-way syncs and collection imports/exports can rewrite `mod` timestamps or revert cards
    back to an earlier state. Queueing a full reset here ensures the next browser render ignores
    the stale timestamp window and rescans the collection from scratch.
    """

    with temporary_collection() as col:
        with patched_addon_state(col) as patched_addon:
            addon = patched_addon
            hooks_module = import_module(f"{addon.__name__}.sibpush.hooks")
            state_module = import_module(f"{addon.__name__}.sibpush.state")
            state_file = state_module.get_state_file_path(col)

            assert state_file is not None

            state_module.sync_last_processed_mod_ts(123)
            state_module.sync_last_sync_mod_ts(456)
            state_module.queue_pending_browser_work(refresh_unmanaged_notes=True)
            state_module.save_persistent_state(col)

            hooks_module.collection_will_temporarily_close(col)

            assert state_module.get_last_processed_mod_ts() == 123
            assert state_module.get_last_sync_mod_ts() == 456
            assert state_module.get_pending_browser_work() == {
                "pending_unsuspend_deck_ids": [],
                "pending_processing_state_reset": True,
                "pending_unmanaged_refresh": False,
            }
            assert state_file.read_text(encoding="utf-8") == (
                '{"last_processed_mod_ts":123,"last_sync_mod_ts":456,'
                '"pending_browser_work":{"pending_processing_state_reset":true,'
                '"pending_unmanaged_refresh":false,"pending_unsuspend_deck_ids":[]}}'
            )


if __name__ == "__main__":
    test_browser_render_delays_the_initial_full_scan()
    test_sync_finish_processes_only_unmanaged_new_notes()
    test_collection_will_temporarily_close_queues_a_full_reset()
