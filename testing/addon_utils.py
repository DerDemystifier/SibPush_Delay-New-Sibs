"""
Utilities for dynamically loading the addon and patching its global state for testing.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from anki.collection import Collection
    from anki.notes import NoteId


# Default interval used for testing immature sibling logic
TEST_INTERVAL = 21


class AddonModule(Protocol):
    """Type protocol representing the test-facing addon facade."""

    mw: Any
    last_checked_state: tuple[str, Sequence["NoteId"]] | None
    config_settings: dict[str, object]
    custom_deck_rules_by_did: dict[str, dict[str, object]]
    ignored_deck_ids: list[str]

    def process_all_notes(self, col: "Collection") -> None: ...

    def process_note(self, col: "Collection", note_id: int, coming_from_reviewer_hook: bool = False) -> None: ...

    SUSPENDED_BY_ADDON_TAG: str


def load_addon_module() -> Any:
    """Load the addon package from the repository root for test execution.

    Returns:
        Any: A small facade that exposes the add-on's shared constants.
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
    state_module = importlib.import_module(f"{module_name}.sibpush.state")
    return SimpleNamespace(
        __name__=module_name,
        __package__=module_name,
        SUSPENDED_BY_ADDON_TAG=state_module.SUSPENDED_BY_ADDON_TAG,
    )


def _load_test_modules() -> tuple[Any, Any, Any]:
    """Load the addon submodules that the test harness patches.

    Returns:
        tuple[Any, Any, Any]: The shared state, config parser, and note-processing modules.
    """

    module_name = "sibpush_test_addon"
    state_module = importlib.import_module(f"{module_name}.sibpush.state")
    parser_module = importlib.import_module(f"{module_name}.sibpush.config.parser")
    notes_module = importlib.import_module(f"{module_name}.sibpush.processing.notes")
    return state_module, parser_module, notes_module


@contextmanager
def patched_addon_state(col: "Collection") -> Generator[AddonModule, None, None]:
    """
    Patch the addon state so processing helpers can run against a test collection.

    This context manager:
    1. Swaps the shared `mw` handle for the provided test collection.
    2. Resets internal state caches (`last_checked_state`).
    3. Configures test-specific settings (`default_interval=21`, no custom deck rules).
    4. Restores original state on exit.
    """
    addon = load_addon_module()
    state_module, parser_module, notes_module = _load_test_modules()
    addon.mw = state_module.mw
    addon.last_checked_state = state_module.last_checked_state
    addon.config_settings = parser_module.config_settings
    addon.custom_deck_rules_by_did = parser_module.custom_deck_rules_by_did
    addon.ignored_deck_ids = parser_module.ignored_deck_ids
    addon.process_all_notes = notes_module.process_all_notes
    addon.process_note = notes_module.process_note

    original_mw = state_module.mw
    original_last_checked_state = state_module.last_checked_state
    original_config = deepcopy(parser_module.config_settings)
    original_ignored_deck_ids = list(parser_module.ignored_deck_ids)
    original_custom_deck_rules_by_did = deepcopy(parser_module.custom_deck_rules_by_did)

    # Mock the main window to provide access to our test collection.
    state_module.mw = SimpleNamespace(col=col)
    state_module.last_checked_state = None
    addon.mw = state_module.mw
    addon.last_checked_state = None

    # Configure test environment.
    parser_module.config_settings.clear()
    parser_module.config_settings.update(deepcopy(original_config))
    parser_module.config_settings["default_interval"] = TEST_INTERVAL
    parser_module.config_settings["custom_deck_rules"] = []
    parser_module.ignored_deck_ids[:] = []
    parser_module.custom_deck_rules_by_did.clear()

    try:
        yield addon
    finally:
        # Restore state to prevent leakage between tests.
        state_module.mw = original_mw
        state_module.last_checked_state = original_last_checked_state
        addon.mw = original_mw
        addon.last_checked_state = original_last_checked_state
        parser_module.config_settings.clear()
        parser_module.config_settings.update(deepcopy(original_config))
        parser_module.ignored_deck_ids[:] = original_ignored_deck_ids
        parser_module.custom_deck_rules_by_did.clear()
        parser_module.custom_deck_rules_by_did.update(deepcopy(original_custom_deck_rules_by_did))
