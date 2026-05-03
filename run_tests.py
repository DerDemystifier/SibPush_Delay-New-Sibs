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


def main() -> None:
    tests = {
        "test_suspend_new_cards_if_immature_sibling_exists": test_suspend_new_cards_if_immature_sibling_exists,
        "test_leaves_one_new_card_when_all_siblings_mature": test_leaves_one_new_card_when_all_siblings_mature,
        "test_leaves_pre_suspended_cards_untouched": test_leaves_pre_suspended_cards_untouched,
    }
    for test_name, test_func in tests.items():
        print("\n\n")
        print(f"[↓ RUNNING TEST ↓] : {test_name}")
        test_func()
        print(f"[↑ TEST COMPLETE ↑] : {test_name}")


if __name__ == "__main__":
    main()
