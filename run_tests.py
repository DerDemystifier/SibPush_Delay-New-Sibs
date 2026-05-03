"""Root test runner for the addon integration tests."""

from testing.test_leave_one_active import run as run_leave_one_active
from testing.test_suspend_when_immature import run as run_suspend_when_immature


def main() -> None:
    tests = [run_suspend_when_immature, run_leave_one_active]
    for test in tests:
        test()


if __name__ == "__main__":
    main()
