"""Root test runner for the addon integration tests."""

from testing.scenarios.test_bury_next_sibling_for_tagged_four_card_notes import (
    test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_custom_deck_interval_overrides_default_interval import (
    test_custom_deck_interval_overrides_default_interval,
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
from testing.scenarios.test_reveal_next_sibling_for_tagged_four_card_notes import (
    test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_resuspend_reintroduced_sibling_for_tagged_four_card_notes import (
    test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes,
)
from testing.scenarios.test_suspend_new_siblings_when_an_immature_review_card_exists import (
    test_suspends_new_siblings_when_an_immature_review_card_exists,
)
from testing.scenarios.test_tag_rule_precedence_and_ignored_deck_behavior import (
    test_ignored_deck_skips_matching_tag_rule,
    test_tag_rule_takes_precedence_over_custom_deck_interval,
)


def main() -> None:
    tests = {
        "test_suspends_new_siblings_when_an_immature_review_card_exists": test_suspends_new_siblings_when_an_immature_review_card_exists,
        "test_keeps_one_new_card_available_when_all_review_siblings_are_mature": test_keeps_one_new_card_available_when_all_review_siblings_are_mature,
        "test_preserves_user_suspended_siblings_without_retagging": test_preserves_user_suspended_siblings_without_retagging,
        "test_process_note_only_updates_the_target_note_from_reviewer_hook": test_process_note_only_updates_the_target_note_from_reviewer_hook,
        "test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes": test_process_all_notes_reveals_the_next_sibling_for_tagged_four_card_notes,
        "test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes": test_process_all_notes_resuspends_a_reintroduced_sibling_for_tagged_four_card_notes,
        "test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes": test_reviewer_hook_buries_the_next_sibling_for_tagged_four_card_notes,
        "test_keeps_one_new_card_available_for_a_fresh_three_card_note": test_keeps_one_new_card_available_for_a_fresh_three_card_note,
        "test_ignores_custom_deck_rule_by_deck_id": test_ignores_custom_deck_rule_by_deck_id,
        "test_migrates_legacy_config_into_custom_deck_rules": test_migrates_legacy_config_into_custom_deck_rules,
        "test_custom_deck_interval_overrides_default_interval": test_custom_deck_interval_overrides_default_interval,
        "test_tag_rule_takes_precedence_over_custom_deck_interval": test_tag_rule_takes_precedence_over_custom_deck_interval,
        "test_ignored_deck_skips_matching_tag_rule": test_ignored_deck_skips_matching_tag_rule,
    }
    for test_name, test_func in tests.items():
        print("\n" * 10)
        print(f"[↓ RUNNING TEST ↓] : {test_name}", end="\n\n")
        test_func()
        print(f"[↑ TEST SUCCESSFUL ↑] : {test_name}")


if __name__ == "__main__":
    main()
