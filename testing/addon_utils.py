"""
Utilities for dynamically loading the addon and patching its global state for testing.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from copy import deepcopy
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from anki.collection import Collection
    from anki.notes import NoteId


# Default interval used for testing immature sibling logic
TEST_INTERVAL = 21


class AddonModule(Protocol):
    """Type protocol representing the public interface of the addon's __init__.py."""

    mw: Any
    last_checked_state: tuple[str, Sequence["NoteId"]] | None
    config_settings: dict[str, object]
    custom_deck_rules_by_did: dict[str, dict[str, object]]
    ignored_deck_ids: list[str]

    def process_all_notes(self, col: "Collection") -> None: ...

    def process_note(self, col: "Collection", note_id: int, coming_from_reviewer_hook: bool = False) -> None: ...

    SUSPENDED_BY_ADDON_TAG: str


def load_addon_module() -> AddonModule:
    """
    Load the addon package from the repository root as a standalone module.

    This avoids requiring the addon to be installed in the Anki addons folder
    during test execution.
    """
    module_name = "sibpush_test_addon"

    for cached_name in [name for name in sys.modules if name == module_name or name.startswith(f"{module_name}.")]:
        sys.modules.pop(cached_name, None)

    module_path = Path(__file__).resolve().parent.parent / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        module_path,
        submodule_search_locations=[str(module_path.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load addon module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return cast(AddonModule, module)


@contextmanager
def patched_addon_state(col: "Collection") -> Generator[AddonModule, None, None]:
    """
    Patch the addon globals so `start_work()` can run against a test collection.

    This context manager:
    1. Swaps `mw.col` for the provided test collection.
    2. Resets internal state caches (last_checked_state).
    3. Configures test-specific settings (default_interval=21, no custom deck rules).
    4. Restores original state on exit.
    """
    addon = load_addon_module()
    original_mw = addon.mw
    original_last_checked_state = addon.last_checked_state
    original_config = deepcopy(addon.config_settings)
    original_ignored_deck_ids = list(addon.ignored_deck_ids)
    original_custom_deck_rules_by_did = deepcopy(addon.custom_deck_rules_by_did)

    # Mock the main window to provide access to our test collection
    addon.mw = SimpleNamespace(col=col)
    addon.last_checked_state = None

    # Configure test environment
    addon.config_settings.clear()
    addon.config_settings.update(deepcopy(original_config))
    addon.config_settings["default_interval"] = TEST_INTERVAL
    addon.config_settings["custom_deck_rules"] = []
    addon.ignored_deck_ids[:] = []
    addon.custom_deck_rules_by_did.clear()

    try:
        yield addon
    finally:
        # Restore state to prevent leakage between tests
        addon.mw = original_mw
        addon.last_checked_state = original_last_checked_state
        addon.config_settings.clear()
        addon.config_settings.update(deepcopy(original_config))
        addon.ignored_deck_ids[:] = original_ignored_deck_ids
        addon.custom_deck_rules_by_did.clear()
        addon.custom_deck_rules_by_did.update(deepcopy(original_custom_deck_rules_by_did))
