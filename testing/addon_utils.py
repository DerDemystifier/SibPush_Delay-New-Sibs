"""
Utilities for dynamically loading the addon and patching its global state for testing.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from anki.collection import BrowserColumns, Collection
    from anki.notes import NoteId


# Default interval used for testing immature sibling logic
TEST_INTERVAL = 21


class AddonModule(Protocol):
    """Type protocol representing the public interface of the addon's __init__.py."""

    mw: Any
    last_checked_state: tuple[str, Sequence["NoteId"]] | None
    due_column: "BrowserColumns.Column | None"
    config_settings: dict[str, object]

    def start_work(self, col: "Collection") -> None: ...

    SUSPENDED_BY_ADDON_TAG: str


def load_addon_module() -> AddonModule:
    """
    Load the addon package from the repository root as a standalone module.

    This avoids requiring the addon to be installed in the Anki addons folder
    during test execution.
    """
    module_name = "sibpush_test_addon"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cast(AddonModule, cached)

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
    3. Configures test-specific settings (interval=21).
    4. Restores original state on exit.
    """
    addon = load_addon_module()
    original_mw = addon.mw
    original_last_checked_state = addon.last_checked_state
    original_due_column = cast("BrowserColumns.Column | None", getattr(addon, "due_column", None))
    original_config = dict(addon.config_settings)

    # Mock the main window to provide access to our test collection
    addon.mw = SimpleNamespace(col=col)
    addon.last_checked_state = None
    addon.due_column = None

    # Configure test environment
    addon.config_settings.clear()
    addon.config_settings.update(original_config)
    addon.config_settings["interval"] = TEST_INTERVAL
    addon.config_settings["ignored_decks"] = []

    try:
        yield addon
    finally:
        # Restore state to prevent leakage between tests
        addon.mw = original_mw
        addon.last_checked_state = original_last_checked_state
        addon.due_column = original_due_column
        addon.config_settings.clear()
        addon.config_settings.update(original_config)
