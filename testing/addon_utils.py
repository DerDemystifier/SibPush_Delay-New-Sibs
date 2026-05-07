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
    last_full_scan_date: str | None
    last_unmanaged_note_ids: Sequence["NoteId"] | None
    last_processed_mod_ts: int | None
    last_sync_mod_ts: int | None
    config_settings: dict[str, object]
    custom_deck_rules_by_did: dict[str, dict[str, object]]
    ignored_deck_ids: list[str]

    def process_all_notes(self, col: "Collection") -> None: ...

    def process_new_unmanaged_notes(self, col: "Collection") -> None: ...

    def process_note(self, col: "Collection", note_id: int, coming_from_reviewer_hook: bool = False) -> None: ...

    def get_state_file_path(self, col: "Collection" | None = None) -> Any: ...

    def load_persistent_state(self, col: "Collection" | None = None) -> dict[str, int | None]: ...

    def save_persistent_state(self, col: "Collection" | None = None) -> dict[str, int | None]: ...

    def reset_persistent_state(self, col: "Collection" | None = None) -> dict[str, int | None]: ...

    def get_last_processed_mod_ts(self) -> int: ...

    def sync_last_processed_mod_ts(self, value: int | None) -> None: ...

    def get_last_sync_mod_ts(self) -> int | None: ...

    def sync_last_sync_mod_ts(self, value: int | None) -> None: ...

    SUSPENDED_BY_ADDON_TAG: str


class FakeAddonManager:
    """Minimal add-on manager stub for config-save tests."""

    def __init__(self, config: dict[str, object] | None = None) -> None:
        self._config = deepcopy(config or {})
        self.writes: list[dict[str, object]] = []

    def getConfig(self, _addon_name: str) -> dict[str, object]:
        return deepcopy(self._config)

    def writeConfig(self, *args: object) -> None:
        if len(args) == 2:
            _, config = args
        elif len(args) == 1:
            (config,) = args
        else:
            raise TypeError("writeConfig expects one or two arguments")

        if not isinstance(config, dict):
            raise TypeError("config must be a dictionary")

        self._config = deepcopy(config)
        self.writes.append(deepcopy(config))

    def setConfig(self, *args: object) -> None:
        self.writeConfig(*args)

    @property
    def config(self) -> dict[str, object]:
        return deepcopy(self._config)


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
def patched_addon_state(
    col: "Collection", addon_manager: FakeAddonManager | None = None
) -> Generator[AddonModule, None, None]:
    """
    Patch the addon state so processing helpers can run against a test collection.

    This context manager:
    1. Swaps the shared `mw` handle for the provided test collection.
    2. Resets internal state caches (`last_full_scan_date` and `last_unmanaged_note_ids`).
    3. Configures test-specific settings (`default_interval=21`, no custom deck rules).
    4. Restores original state on exit.
    """
    addon = load_addon_module()
    state_module, parser_module, notes_module = _load_test_modules()
    addon.mw = state_module.mw
    addon.last_full_scan_date = state_module.last_full_scan_date
    addon.last_unmanaged_note_ids = state_module.last_unmanaged_note_ids
    addon.last_processed_mod_ts = state_module.last_processed_mod_ts
    addon.last_sync_mod_ts = state_module.last_sync_mod_ts
    addon.config_settings = parser_module.config_settings
    addon.custom_deck_rules_by_did = parser_module.custom_deck_rules_by_did
    addon.ignored_deck_ids = parser_module.ignored_deck_ids
    addon.process_all_notes = notes_module.process_all_notes
    addon.process_new_unmanaged_notes = notes_module.process_new_unmanaged_notes
    addon.process_note = notes_module.process_note
    addon.get_state_file_path = state_module.get_state_file_path
    addon.load_persistent_state = state_module.load_persistent_state
    addon.save_persistent_state = state_module.save_persistent_state
    addon.reset_persistent_state = state_module.reset_persistent_state
    addon.get_last_processed_mod_ts = state_module.get_last_processed_mod_ts
    addon.sync_last_processed_mod_ts = state_module.sync_last_processed_mod_ts
    addon.get_last_sync_mod_ts = state_module.get_last_sync_mod_ts
    addon.sync_last_sync_mod_ts = state_module.sync_last_sync_mod_ts

    original_mw = state_module.mw
    original_last_full_scan_date = state_module.last_full_scan_date
    original_last_unmanaged_note_ids = state_module.last_unmanaged_note_ids
    original_last_processed_mod_ts = state_module.last_processed_mod_ts
    original_last_sync_mod_ts = state_module.last_sync_mod_ts
    original_config = deepcopy(parser_module.config_settings)
    original_ignored_deck_ids = list(parser_module.ignored_deck_ids)
    original_custom_deck_rules_by_did = deepcopy(parser_module.custom_deck_rules_by_did)

    # Mock the main window to provide access to our test collection.
    state_module.mw = SimpleNamespace(col=col, addonManager=addon_manager)
    state_module.last_full_scan_date = None
    state_module.last_unmanaged_note_ids = None
    state_module.last_processed_mod_ts = None
    state_module.last_sync_mod_ts = None
    addon.mw = state_module.mw
    addon.last_full_scan_date = None
    addon.last_unmanaged_note_ids = None
    addon.last_processed_mod_ts = None
    addon.last_sync_mod_ts = None

    # Configure test environment.
    parser_module.config_settings.clear()
    parser_module.config_settings.update(deepcopy(original_config))
    parser_module.config_settings["default_interval"] = TEST_INTERVAL
    parser_module.config_settings["custom_deck_rules"] = []
    parser_module.config_settings["tag_rules"] = {}
    parser_module.ignored_deck_ids[:] = []
    parser_module.custom_deck_rules_by_did.clear()

    try:
        yield addon
    finally:
        # Restore state to prevent leakage between tests.
        state_module.mw = original_mw
        state_module.last_full_scan_date = original_last_full_scan_date
        state_module.last_unmanaged_note_ids = original_last_unmanaged_note_ids
        state_module.last_processed_mod_ts = original_last_processed_mod_ts
        state_module.last_sync_mod_ts = original_last_sync_mod_ts
        addon.mw = original_mw
        addon.last_full_scan_date = original_last_full_scan_date
        addon.last_unmanaged_note_ids = original_last_unmanaged_note_ids
        addon.last_processed_mod_ts = original_last_processed_mod_ts
        addon.last_sync_mod_ts = original_last_sync_mod_ts
        parser_module.config_settings.clear()
        parser_module.config_settings.update(deepcopy(original_config))
        parser_module.ignored_deck_ids[:] = original_ignored_deck_ids
        parser_module.custom_deck_rules_by_did.clear()
        parser_module.custom_deck_rules_by_did.update(deepcopy(original_custom_deck_rules_by_did))
