# Spec: fast CI on every push (recipes-cms #34)

Sibling change: recipes-frontend #17 (same spec there).

## Why

- Catch regressions on every push to every branch, not at PR or release time.
- Full-stack e2e stays in recipes-infrastructure on releases.

## Goals

- New `.github/workflows/ci.yml`, triggered on `push` to all branches (not tags; `build.yml` keeps tags).
- Steps: checkout, set up uv with Python 3.14, `uv sync`, `uv run invoke lint`, `uv run invoke test`.
- Tests use SQLite and `settings.test` defaults: no Docker, no `.env`, no secrets.
- Least permissions (`contents: read`).
- Docs: CLAUDE.md and README.md stop saying "no CI runs tests"; say CI runs lint and the SQLite tests on every push, and Postgres-specific checks still need `invoke test --postgres` locally.

## Non-goals

- Postgres tests in CI (the `LOWER(email)` index test stays skipped on SQLite).
- Compose stack or e2e in this repo.
- A separate `pull_request` trigger (a PR's head commit is already a push).

## Calls made by Claude (approved by user)

- Lint (ruff + mypy) runs in CI too, not only tests.
- No `pull_request` trigger, to avoid duplicate runs.

## Left to the builder

- Action versions (e.g. `astral-sh/setup-uv`), caching, step names.
- Whether the invoke tasks need a non-TTY tweak in CI (`pty` already follows `isatty`).
