"""Anki add-on entrypoint that registers the add-on hooks."""

from __future__ import annotations

from .sibpush.hooks import register_hooks


register_hooks()
