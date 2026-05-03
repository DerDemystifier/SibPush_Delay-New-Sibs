"""
Utilities for creating and managing isolated Anki collections for integration testing.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anki.collection import Collection


@contextmanager
def temporary_collection() -> Generator["Collection", None, None]:
    """
    Create a temporary on-disk Anki collection and clean it up afterward.

    We use a real disk file instead of ':memory:' because some Anki operations
    expect a filesystem path and ':memory:' can behave inconsistently in certain
    pylib versions.
    """
    from anki.collection import Collection

    with tempfile.TemporaryDirectory() as tmpdir:
        col_path = Path(tmpdir) / "collection.anki2"
        col = Collection(str(col_path))
        try:
            yield col
        finally:
            # Ensure the collection is closed so the directory can be deleted on Windows
            col.close()
