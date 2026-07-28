"""Root test runner for the addon integration tests."""

import traceback

from testing.scenarios.test_bury_next_sibling_for_non_ignored_four_card_notes import (
    test_reviewer_hook_buries_the_next_sibling_for_non_ignored_four_card_notes,
)
from testing.scenarios.test_custom_deck_interval_overrides_default_interval import (
    test_custom_deck_interval_overrides_default_interval,
)
from testing.scenarios.test_deck_actions_save_and_refresh import (
    test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored,
)
from testing.scenarios.test_addon_delete_unsuspends_all_cards import (
    test_on_addon_delete_restores_only_owned_new_cards_before_deletion,
)
from testing.scenarios.test_deck_browser_menu_actions import (
    test_deck_browser_submenu_toggles_ignore_and_sets_interval,
)
from testing.scenarios.test_card_browser_menu_actions import (
    test_card_browser_ignore_toggle_preserves_manual_suspension,
)
from testing.scenarios.test_ignore_custom_deck_rule_by_deck_id import (
    test_ignores_custom_deck_rule_by_deck_id,
)
from testing.scenarios.test_keep_one_new_card_available_for_a_fresh_three_card_note import (
    test_keeps_one_new_card_available_for_a_fresh_three_card_note,
)
from testing.scenarios.test_keep_one_new_card_available_when_all_review_siblings_are_mature import (
    test_keeps_one_new_card_available_when_all_review_siblings_are_mature,
)
from testing.scenarios.test_manual_unsuspend_reprocesses_non_ignored_new_card import (
    test_manual_unsuspend_of_non_ignored_new_card_is_reprocessed_and_suspended_again,
)
from testing.scenarios.test_migrate_legacy_config_into_custom_deck_rules import (
    test_migrates_legacy_config_into_custom_deck_rules,
)
from testing.scenarios.test_config_state_invalidation import (
    test_ignoring_a_deck_keeps_persistent_state,
    test_changing_tag_rules_resets_persistent_state,
    test_unignoring_a_deck_resets_persistent_state,
)
from testing.scenarios.test_recently_modified_note_ids import (
    test_get_modified_note_ids_since_returns_recent_note_and_card_changes,
)
from testing.scenarios.test_timestamp_based_browser_scan import (
    test_browser_render_uses_the_older_timestamp_watermark,
    test_browser_render_runs_unmanaged_refresh_after_partial_scan,
    test_browser_render_clears_stale_sync_watermark_after_scan,
    test_process_modified_notes_persists_the_processed_watermark,
    test_sync_did_finish_persists_the_sync_watermark,
)
from testing.scenarios.test_process_a_single_note_without_touching_other_notes import (
    test_process_note_only_updates_the_target_note_from_reviewer_hook,
)
from testing.scenarios.test_preserve_user_suspended_siblings import (
    test_preserves_user_suspended_siblings_without_retagging,
)
from testing.scenarios.test_clear_ignored_flag_when_last_sibling_is_restored import (
    test_process_all_notes_restores_the_last_sibling_after_suspension,
    test_reviewer_hook_buries_the_last_sibling_after_restoring_it,
)
from testing.scenarios.test_reveal_next_sibling_for_non_ignored_four_card_notes import (
    test_process_all_notes_reveals_the_next_sibling_for_non_ignored_four_card_notes,
)
from testing.scenarios.test_clear_ignored_flag_for_user_unsuspended_trailing_card import (
    test_process_all_notes_resuspends_later_new_sibling_after_manual_unsuspend,
)
from testing.scenarios.test_suspend_new_siblings_when_an_immature_review_card_exists import (
    test_suspends_new_siblings_when_an_immature_review_card_exists,
)
from testing.scenarios.test_suspension_markers import (
    test_sibpush_marks_only_cards_it_suspends,
    test_manual_unsuspend_retains_provenance_until_sibpush_restores_card,
    test_ignore_marker_preserves_provenance_queue_and_unrelated_data,
    test_deck_cleanup_restores_owned_card_and_removes_only_suspension_marker,
    test_cleanup_preserves_card_with_both_markers_even_when_delete_confirms_clear,
    test_legacy_ignore_migration_preserves_third_party_data_and_is_idempotent,
    test_legacy_suspension_tag_migration_marks_only_currently_suspended_cards,
    test_one_ignored_sibling_does_not_hide_other_eligible_siblings,
    test_target_build_custom_data_search_syntax_is_positive_only,
    test_scheduler_failure_does_not_infer_suspension_provenance,
    test_scheduler_failure_preserves_restoration_provenance_after_partial_success,
    test_direct_legacy_ignore_clear_preserves_new_marker_and_third_party_data,
    test_async_clear_all_ignored_markers_processes_every_candidate_in_chunks,
    test_normal_promotion_removes_suspension_provenance,
    test_async_deck_cleanup_stops_when_deck_is_unignored_between_chunks,
    test_async_deck_cleanup_skips_cards_moved_before_their_chunk,
)
from testing.scenarios.test_unsuspend_cards_when_deck_becomes_ignored import (
    test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck,
    test_unsuspend_all_addon_cards_in_deck_restores_only_owned_new_cards,
)
from testing.scenarios.test_tag_rule_precedence_and_ignored_deck_behavior import (
    test_ignored_deck_skips_matching_tag_rule,
    test_tag_rule_takes_precedence_over_custom_deck_interval,
)
from testing.scenarios.test_breaking_change_recovery import (
    test_needs_breaking_change_recovery_uses_the_version_floor,
    test_browser_render_performs_recovery_when_version_is_missing,
    test_browser_render_reprocesses_legacy_suspension_tags_before_scan,
    test_collection_did_load_skips_recovery_when_future_version_is_stored,
)
from testing.scenarios.test_chunked_runner import (
    test_run_chunked_yields_between_batches_and_reports_progress,
    test_run_chunked_calls_completion_when_processing_fails,
    test_run_chunked_stops_before_a_stale_next_batch,
    test_run_chunked_completes_empty_work_as_success,
)
from testing.scenarios.test_suspend_new_siblings_when_an_immature_review_card_exists import (
    test_suspended_immature_review_card_does_not_block_new_siblings,
)


import io
from contextlib import redirect_stdout

tests = {
    "test_suspends_new_siblings_when_an_immature_review_card_exists": test_suspends_new_siblings_when_an_immature_review_card_exists,
    "test_keeps_one_new_card_available_when_all_review_siblings_are_mature": test_keeps_one_new_card_available_when_all_review_siblings_are_mature,
    "test_preserves_user_suspended_siblings_without_retagging": test_preserves_user_suspended_siblings_without_retagging,
    "test_process_all_notes_restores_the_last_sibling_after_suspension": test_process_all_notes_restores_the_last_sibling_after_suspension,
    "test_reviewer_hook_buries_the_last_sibling_after_restoring_it": test_reviewer_hook_buries_the_last_sibling_after_restoring_it,
    "test_process_note_only_updates_the_target_note_from_reviewer_hook": test_process_note_only_updates_the_target_note_from_reviewer_hook,
    "test_process_all_notes_reveals_the_next_sibling_for_non_ignored_four_card_notes": test_process_all_notes_reveals_the_next_sibling_for_non_ignored_four_card_notes,
    "test_manual_unsuspend_of_non_ignored_new_card_is_reprocessed_and_suspended_again": test_manual_unsuspend_of_non_ignored_new_card_is_reprocessed_and_suspended_again,
    "test_process_all_notes_resuspends_later_new_sibling_after_manual_unsuspend": test_process_all_notes_resuspends_later_new_sibling_after_manual_unsuspend,
    "test_reviewer_hook_buries_the_next_sibling_for_non_ignored_four_card_notes": test_reviewer_hook_buries_the_next_sibling_for_non_ignored_four_card_notes,
    "test_keeps_one_new_card_available_for_a_fresh_three_card_note": test_keeps_one_new_card_available_for_a_fresh_three_card_note,
    "test_ignores_custom_deck_rule_by_deck_id": test_ignores_custom_deck_rule_by_deck_id,
    "test_migrates_legacy_config_into_custom_deck_rules": test_migrates_legacy_config_into_custom_deck_rules,
    "test_ignoring_a_deck_keeps_persistent_state": test_ignoring_a_deck_keeps_persistent_state,
    "test_changing_tag_rules_resets_persistent_state": test_changing_tag_rules_resets_persistent_state,
    "test_unignoring_a_deck_resets_persistent_state": test_unignoring_a_deck_resets_persistent_state,
    "test_get_modified_note_ids_since_returns_recent_note_and_card_changes": test_get_modified_note_ids_since_returns_recent_note_and_card_changes,
    "test_browser_render_uses_the_older_timestamp_watermark": test_browser_render_uses_the_older_timestamp_watermark,
    "test_browser_render_runs_unmanaged_refresh_after_partial_scan": test_browser_render_runs_unmanaged_refresh_after_partial_scan,
    "test_browser_render_clears_stale_sync_watermark_after_scan": test_browser_render_clears_stale_sync_watermark_after_scan,
    "test_process_modified_notes_persists_the_processed_watermark": test_process_modified_notes_persists_the_processed_watermark,
    "test_sync_did_finish_persists_the_sync_watermark": test_sync_did_finish_persists_the_sync_watermark,
    "test_custom_deck_interval_overrides_default_interval": test_custom_deck_interval_overrides_default_interval,
    "test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored": test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored,
    "test_on_addon_delete_restores_only_owned_new_cards_before_deletion": test_on_addon_delete_restores_only_owned_new_cards_before_deletion,
    "test_deck_browser_submenu_toggles_ignore_and_sets_interval": test_deck_browser_submenu_toggles_ignore_and_sets_interval,
    "test_card_browser_ignore_toggle_preserves_manual_suspension": test_card_browser_ignore_toggle_preserves_manual_suspension,
    "test_tag_rule_takes_precedence_over_custom_deck_interval": test_tag_rule_takes_precedence_over_custom_deck_interval,
    "test_ignored_deck_skips_matching_tag_rule": test_ignored_deck_skips_matching_tag_rule,
    "test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck": test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck,
    "test_unsuspend_all_addon_cards_in_deck_restores_only_owned_new_cards": test_unsuspend_all_addon_cards_in_deck_restores_only_owned_new_cards,
    "test_needs_breaking_change_recovery_uses_the_version_floor": test_needs_breaking_change_recovery_uses_the_version_floor,
    "test_browser_render_performs_recovery_when_version_is_missing": test_browser_render_performs_recovery_when_version_is_missing,
    "test_browser_render_reprocesses_legacy_suspension_tags_before_scan": test_browser_render_reprocesses_legacy_suspension_tags_before_scan,
    "test_collection_did_load_skips_recovery_when_future_version_is_stored": test_collection_did_load_skips_recovery_when_future_version_is_stored,
    "test_run_chunked_yields_between_batches_and_reports_progress": test_run_chunked_yields_between_batches_and_reports_progress,
    "test_run_chunked_calls_completion_when_processing_fails": test_run_chunked_calls_completion_when_processing_fails,
    "test_run_chunked_stops_before_a_stale_next_batch": test_run_chunked_stops_before_a_stale_next_batch,
    "test_run_chunked_completes_empty_work_as_success": test_run_chunked_completes_empty_work_as_success,
    "test_suspended_immature_review_card_does_not_block_new_siblings": test_suspended_immature_review_card_does_not_block_new_siblings,
    "test_sibpush_marks_only_cards_it_suspends": test_sibpush_marks_only_cards_it_suspends,
    "test_manual_unsuspend_retains_provenance_until_sibpush_restores_card": test_manual_unsuspend_retains_provenance_until_sibpush_restores_card,
    "test_ignore_marker_preserves_provenance_queue_and_unrelated_data": test_ignore_marker_preserves_provenance_queue_and_unrelated_data,
    "test_deck_cleanup_restores_owned_card_and_removes_only_suspension_marker": test_deck_cleanup_restores_owned_card_and_removes_only_suspension_marker,
    "test_cleanup_preserves_card_with_both_markers_even_when_delete_confirms_clear": test_cleanup_preserves_card_with_both_markers_even_when_delete_confirms_clear,
    "test_legacy_ignore_migration_preserves_third_party_data_and_is_idempotent": test_legacy_ignore_migration_preserves_third_party_data_and_is_idempotent,
    "test_legacy_suspension_tag_migration_marks_only_currently_suspended_cards": test_legacy_suspension_tag_migration_marks_only_currently_suspended_cards,
    "test_one_ignored_sibling_does_not_hide_other_eligible_siblings": test_one_ignored_sibling_does_not_hide_other_eligible_siblings,
    "test_target_build_custom_data_search_syntax_is_positive_only": test_target_build_custom_data_search_syntax_is_positive_only,
    "test_scheduler_failure_does_not_infer_suspension_provenance": test_scheduler_failure_does_not_infer_suspension_provenance,
    "test_scheduler_failure_preserves_restoration_provenance_after_partial_success": test_scheduler_failure_preserves_restoration_provenance_after_partial_success,
    "test_direct_legacy_ignore_clear_preserves_new_marker_and_third_party_data": test_direct_legacy_ignore_clear_preserves_new_marker_and_third_party_data,
    "test_async_clear_all_ignored_markers_processes_every_candidate_in_chunks": test_async_clear_all_ignored_markers_processes_every_candidate_in_chunks,
    "test_normal_promotion_removes_suspension_provenance": test_normal_promotion_removes_suspension_provenance,
    "test_async_deck_cleanup_stops_when_deck_is_unignored_between_chunks": test_async_deck_cleanup_stops_when_deck_is_unignored_between_chunks,
    "test_async_deck_cleanup_skips_cards_moved_before_their_chunk": test_async_deck_cleanup_skips_cards_moved_before_their_chunk,
}


prints_hidden = True  # Set this to False to print the captured stdout of successful tests, True to only print failed tests' output.


def main() -> None:
    if prints_hidden:
        for test_name, test_func in tests.items():
            f = io.StringIO()
            try:
                with redirect_stdout(f):
                    test_func()
            except Exception:
                print("\n" * 10)
                print(f"[↓ TEST FAILED ↓] : {test_name}")
                print(f.getvalue())
                print(traceback.format_exc())
                raise

        print("\n" * 10)
        print("All tests successful!")
    else:
        for test_name, test_func in tests.items():
            print("\n" * 10)
            print(f"[↓ RUNNING TEST ↓] : {test_name}", end="\n\n")
            test_func()
            print(f"[↑ TEST SUCCESSFUL ↑] : {test_name}")


if __name__ == "__main__":
    main()
