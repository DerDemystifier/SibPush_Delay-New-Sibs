"""Root test runner for the addon integration tests."""

from testing.test_leave_one_active import (
    test_leaves_one_new_card_when_all_siblings_mature,
)
from testing.test_already_suspended_cards import (
    test_leaves_pre_suspended_cards_untouched,
)
from testing.test_suspend_when_immature import (
    test_suspend_new_cards_if_immature_sibling_exists,
)
from testing.test_process_single_note import (
    test_process_single_note_while_reviewing,
)
from testing.test_process_all_notes_with_tagged_four_card_note import (
    test_process_all_notes_unsuspends_the_third_card_for_a_tagged_four_card_note,
)
from testing.test_process_note_reviewer_hook_tagged_four_card_note import (
    test_process_note_buries_the_third_card_when_called_from_reviewer_hook,
)
from testing.test_all_new_cards_one_available import (
    test_start_work_keeps_one_card_available_for_a_fresh_three_card_note,
)
from testing.test_ignored_custom_deck_rule import (
    test_ignored_custom_deck_rule_uses_deck_id,
)
from testing.test_legacy_config_migration import (
    test_legacy_config_migrates_to_new_schema,
)
from testing.test_custom_deck_interval import (
    test_custom_deck_interval_overrides_default_threshold,
)


def main() -> None:
    tests = {
        "test_suspend_new_cards_if_immature_sibling_exists": test_suspend_new_cards_if_immature_sibling_exists,
        "test_leaves_one_new_card_when_all_siblings_mature": test_leaves_one_new_card_when_all_siblings_mature,
        "test_leaves_pre_suspended_cards_untouched": test_leaves_pre_suspended_cards_untouched,
        "test_process_note_only_updates_the_requested_note": test_process_single_note_while_reviewing,
        "test_process_all_notes_unsuspends_the_third_card_for_a_tagged_four_card_note": test_process_all_notes_unsuspends_the_third_card_for_a_tagged_four_card_note,
        "test_process_note_buries_the_third_card_when_called_from_reviewer_hook": test_process_note_buries_the_third_card_when_called_from_reviewer_hook,
        "test_start_work_keeps_one_card_available_for_a_fresh_three_card_note": test_start_work_keeps_one_card_available_for_a_fresh_three_card_note,
        "test_ignored_custom_deck_rule_uses_deck_id": test_ignored_custom_deck_rule_uses_deck_id,
        "test_legacy_config_migrates_to_new_schema": test_legacy_config_migrates_to_new_schema,
        "test_custom_deck_interval_overrides_default_threshold": test_custom_deck_interval_overrides_default_threshold,
    }
    for test_name, test_func in tests.items():
        print("\n" * 10)
        print(f"[↓ RUNNING TEST ↓] : {test_name}")
        test_func()
        print(f"[↑ TEST SUCCESSFUL ↑] : {test_name}")


if __name__ == "__main__":
    main()
