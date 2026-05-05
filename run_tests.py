"""Root test runner for the addon integration tests."""

import traceback

from testing.scenarios.test_bury_next_sibling_for_tagged_four_card_notes import (
    test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_custom_deck_interval_overrides_default_interval import (
    test_custom_deck_interval_overrides_default_interval,
)
from testing.scenarios.test_deck_actions_save_and_refresh import (
    test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored,
)
from testing.scenarios.test_deck_browser_menu_actions import (
    test_deck_browser_submenu_toggles_ignore_and_sets_interval,
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
from testing.scenarios.test_migrate_legacy_config_into_custom_deck_rules import (
    test_migrates_legacy_config_into_custom_deck_rules,
)
from testing.scenarios.test_process_a_single_note_without_touching_other_notes import (
    test_process_note_only_updates_the_target_note_from_reviewer_hook,
)
from testing.scenarios.test_preserve_user_suspended_siblings import (
    test_preserves_user_suspended_siblings_without_retagging,
)
from testing.scenarios.test_remove_suspended_tag_when_last_sibling_is_restored import (
    test_process_all_notes_removes_the_suspension_tag_after_restoring_the_last_sibling,
    test_reviewer_hook_removes_the_suspension_tag_after_burying_the_last_sibling,
)
from testing.scenarios.test_reveal_next_sibling_for_tagged_four_card_notes import (
    test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_resuspend_reintroduced_sibling_for_tagged_four_card_notes import (
    test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_suspend_new_siblings_when_an_immature_review_card_exists import (
    test_suspends_new_siblings_when_an_immature_review_card_exists,
)
from testing.scenarios.test_unsuspend_cards_when_deck_becomes_ignored import (
    test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck,
)
from testing.scenarios.test_tag_rule_precedence_and_ignored_deck_behavior import (
    test_ignored_deck_skips_matching_tag_rule,
    test_tag_rule_takes_precedence_over_custom_deck_interval,
)

import io
from contextlib import redirect_stdout

tests = {
    "test_suspends_new_siblings_when_an_immature_review_card_exists": test_suspends_new_siblings_when_an_immature_review_card_exists,
    "test_keeps_one_new_card_available_when_all_review_siblings_are_mature": test_keeps_one_new_card_available_when_all_review_siblings_are_mature,
    "test_preserves_user_suspended_siblings_without_retagging": test_preserves_user_suspended_siblings_without_retagging,
    "test_process_all_notes_removes_the_suspension_tag_after_restoring_the_last_sibling": test_process_all_notes_removes_the_suspension_tag_after_restoring_the_last_sibling,
    "test_reviewer_hook_removes_the_suspension_tag_after_burying_the_last_sibling": test_reviewer_hook_removes_the_suspension_tag_after_burying_the_last_sibling,
    "test_process_note_only_updates_the_target_note_from_reviewer_hook": test_process_note_only_updates_the_target_note_from_reviewer_hook,
    "test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes": test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes,
    "test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes": test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes,
    "test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes": test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes,
    "test_keeps_one_new_card_available_for_a_fresh_three_card_note": test_keeps_one_new_card_available_for_a_fresh_three_card_note,
    "test_ignores_custom_deck_rule_by_deck_id": test_ignores_custom_deck_rule_by_deck_id,
    "test_migrates_legacy_config_into_custom_deck_rules": test_migrates_legacy_config_into_custom_deck_rules,
    "test_custom_deck_interval_overrides_default_interval": test_custom_deck_interval_overrides_default_interval,
    "test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored": test_update_custom_deck_rule_unsuspends_cards_when_deck_becomes_ignored,
    "test_deck_browser_submenu_toggles_ignore_and_sets_interval": test_deck_browser_submenu_toggles_ignore_and_sets_interval,
    "test_tag_rule_takes_precedence_over_custom_deck_interval": test_tag_rule_takes_precedence_over_custom_deck_interval,
    "test_ignored_deck_skips_matching_tag_rule": test_ignored_deck_skips_matching_tag_rule,
    "test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck": test_on_config_save_unsuspends_addon_cards_for_newly_ignored_deck,
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
