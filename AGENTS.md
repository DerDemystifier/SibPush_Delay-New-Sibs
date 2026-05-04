# SibPush_Delay-New-Sibs agent notes

## What this project is

- Anki desktop add-on that delays new sibling cards until older siblings are mature, then restores them later.
- Runtime depends on Anki's `aqt` / `anki` modules; keep import-time behavior light and Anki-friendly.

## Repo boundaries

- `__init__.py` should stay thin: register hooks only.
- Real logic lives under `sibpush/`.
- Shared runtime state belongs in `sibpush/state.py`; do not hard-bind submodules directly to `aqt.mw` when a runtime getter is available.
- Avoid reintroducing root compatibility wrappers or export indirection unless a specific migration/test need requires it.
- Legacy config migration is temporary and isolated in `sibpush/config/migration.py`.

## When changing behavior

- Keep `did` as the stable identifier for deck-specific config; `name` is for readability only.
- If config schema changes, update `config.json` and `config.md` together.
- Debug logging writes to `log.txt` beside the add-on when `debug` is enabled.
- Prefer small, focused changes that preserve the current package layout.

## Testing and validation

- Primary validation command: `python run_tests.py`
- Run it from the Anki interpreter virtualenv, not system Python.
- Manual Anki testing is the real runtime check; there is no CI in this repo.
- For tests, use the helpers in `testing/` and a real temporary `.anki2` file instead of `Collection(':memory:')`.

## Link, don't duplicate

- [`README.md`](./README.md) — user-facing overview and behavior.
- [`config.md`](./config.md) — canonical configuration reference.
- [`run_tests.py`](./run_tests.py) — test entrypoint.
- [`testing/addon_utils.py`](./testing/addon_utils.py) — test harness and patched state setup.
- [`docs/README.html`](./docs/README.html) — generated rendered docs, if needed.
