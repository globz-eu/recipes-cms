# Plan: fast CI on every push (recipes-cms #34)

Spec: `docs/plans/2026-11-08-ci-on-every-push.spec.md`.

## Context

- `build.yml` runs on tags only; nothing runs lint or tests on push.
- `invoke lint` sets `AUTH_PROVIDERS=local` itself (`tasks.py:53`); no env needed.
- `invoke test` runs `manage.py test` in `src/`; `settings.test` supplies dummy secrets and SQLite.
- Need to confirm `manage.py` picks `settings.test` without `.env` (check `src/manage.py` default).
- `pty=sys.stdout.isatty()` is already false in CI; no task change.

## Files to change

- New `.github/workflows/ci.yml`.
- `CLAUDE.md:13`: replace "no CI runs tests".
- `README.md:265`: same.

## Acceptance criteria

1. `ci.yml` triggers on `push` to all branches, not tags, no `pull_request`.
2. Workflow permissions are `contents: read` only.
3. Steps: checkout, setup-uv (Python 3.14), `uv sync`, `uv run invoke lint`, `uv run invoke test`.
4. No Docker, `.env` or secrets used; tests run on SQLite.
5. A lint or test failure fails the job.
6. CLAUDE.md and README.md say CI runs lint and SQLite tests on every push.
7. Docs still say Postgres checks need `invoke test --postgres` locally.
8. `build.yml` unchanged.

## Implementation steps

1. Confirm `manage.py` default settings module; if not `settings.test`, set `DJANGO_SETTINGS_MODULE` in the test step env.
2. Add `ci.yml`: `on.push.branches: ["**"]`, `actions/checkout@v4`, `astral-sh/setup-uv@v10.3.3` (no floating major tag exists) with `python-version: "3.14"` and `enable-cache: true`.
3. Add steps `uv sync --locked`, `uv run invoke lint`, `uv run invoke test`.
4. Commit: "Run lint and tests in CI on every push".
5. Update the CLAUDE.md and README.md wording; commit: "Document CI lint and tests".

## Verification

- Clean-env run: `env -i HOME="$HOME" PATH="$PATH" sh -c 'uv sync --locked && uv run invoke lint && uv run invoke test'` from a fresh clone without `.env`.
- Run `actionlint .github/workflows/ci.yml` if installed; otherwise a YAML parse check.
- Push the branch and confirm the Actions run is green.
- Check that a tag push does not trigger `ci.yml`.

## Risks and open questions

- `setup-uv` pinned to v10.3.3, its current release when implemented.
- Python 3.14 availability via setup-uv; fall back to `.python-version` if not.
- Any `uv.lock` drift fails `--locked`; accepted as intended.
- Open: add `concurrency` cancel-in-progress for superseded pushes? Left out (YAGNI).
