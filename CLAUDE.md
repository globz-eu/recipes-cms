# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@~/.claude/architectures/recipes.md

## Commands

The dev stack lives in the sibling repo recipes-infrastructure (`dev/compose.yml`, `scripts/dev-stack.sh`); this repo only adds `compose.dev.yml`, which builds this checkout and syncs `src/` into the `wagtail` container. Python deps are managed with `uv` (Python 3.14+). The stack needs `.env`: in the main checkout `cp ../recipes-infrastructure/dev/.env.example .env && chmod 600 .env`, then fill in the secrets (extra worktrees: `dev-stack.sh env`). For a fresh stack, see README.md "Provisioning Garage". `RECIPES_INFRA_DIR` in `.env` only helps once `.env` exists, so use the shell for the first setup. The tests do not need `.env`.

Tests run on the host with SQLite by default (no Docker, no `.env`). Changes touching email uniqueness (the `LOWER(email)` index, `oidc_auth` migration 0001, `enforce_email_ownership`, user forms) or other Postgres-specific behaviour must also pass `uv run invoke test --postgres`: CI runs only lint and the SQLite tests, and the index test is skipped on SQLite.

Start the stack with `uv run invoke dev`, never plain `docker compose up -d`: only watch mode syncs `src/`, so otherwise the container runs stale code. Other compose commands: `$DEV_STACK compose ARGS` with `DEV_STACK="${RECIPES_INFRA_DIR:-<main checkout>/../recipes-infrastructure}"/scripts/dev-stack.sh`.

```bash
uv run invoke dev [--build]         # start the stack in watch mode
uv run invoke down [--volumes]      # stop the stack
uv run invoke test --label=recipes  # SQLite on the host; --postgres: in the container (then run invoke down)
uv run invoke format                # ruff check --fix + ruff format
uv run invoke lint                  # ruff check + format --check + mypy
uv run invoke bump --part minor     # bump version, commit, tag vX.Y.Z (the tag push triggers the image build)

(cd src && uv run manage.py test recipes.tests.test_bulk_upload.SomeTest.test_name)  # single test
$DEV_STACK compose exec wagtail python manage.py import_recipes recipes.json
```

`manage.py` lives in `src/`. Settings are `recipe_cms.settings.{dev,production}` (both extend `base`).

## Architecture

Django + Wagtail headless CMS: Wagtail admin for editors, DRF API under `/api/` consumed by `../recipes-frontend`.

- **`oidc_auth`**: pluggable sign-in. `AUTH_PROVIDERS` (`local`, `auth0`, `zitadel`; default `local,auth0`) selects the methods; settings fail at import if an enabled provider's variables are missing or blank (`config.py`), and zitadel also needs `ZITADEL_ROLE_ORG_ID`. Social logins start with a POST (CSRF token and `next` as form fields; GET is 405). Invariants: one email, one provider (unique `LOWER(email)` index, `enforce_email_ownership`); the Zitadel org check fails closed (`enforce_zitadel_org`); refusals are `LoginRefused` subclasses (`exceptions.py`), each with an `auth_error` code that `LoginRefusedMiddleware` turns into a redirect. `LocalLoginView` and `safe_redirect_url` follow `next` only to the request host and `ALLOWED_REDIRECT_HOSTS`, and require HTTPS on secure requests. Without `local`, `PermissionsOnlyBackend` replaces `ModelBackend`. Roles: provider readers in `providers.py`, mapped through `ROLE_GROUP_MAP` (`settings/base.py`); `admin` grants superuser/staff. Details: `pipeline.py`, `middleware.py`, `redirects.py`; `tests/login_harness.py` is the shared test login helper.
- **`home`**: `HomePage` (one per locale) is the only allowed parent of `RecipePage`. `locales.get_requested_locale` implements `?locale=`. Also the `ensure_admin` and `ensure_users` commands, `/api/dev-login/` (404 unless `DEV_PASSWORD_LOGIN`, set only by `settings/dev.py`) and the shared permission class.
- **`recipes`**: `RecipePage` with orderable `RecipeIngredient` children. Bulk upload: `serializers.py` (validation), `importer.py` (service shared by the API view and `import_recipes`), `views.py`.
- **`image_auth`**: `serve_media` streams media from S3 to authorized users; nginx proxies `/media/` to it.
- **nginx** config lives in recipes-infrastructure; dev settings read `DEV_FRONTEND_ORIGINS` (default `http://localhost:5173`) for `CSRF_TRUSTED_ORIGINS` and `ALLOWED_REDIRECT_HOSTS` (env var in production).

### Multilingual model

Wagtail i18n with `en` (default), `de`, `fr`, `nl`. Each locale has its own HomePage tree (depth 2); translations of a recipe live under their locale's HomePage and share a `translation_key`. Locales and homepages come from data migrations (`home/migrations/0002`, `0004`, `0005`), which tests and the importer rely on.

### Bulk import (`recipes/importer.py`)

- Recipes match by `(slug, locale)`; existing pages are fully overwritten (ingredients too), new ones are created under the locale's HomePage.
- All-or-nothing: an outer `transaction.atomic()` wraps per-group savepoints; errors are collected per group index, then everything is rolled back and `RecipeImportError` raised.
- With a user (API), Wagtail page permissions apply and users who can't publish leave a draft revision; the command passes no user and skips checks.
- Edits go through `save_revision` then `publish`/`unpublish`, keeping revision history.

### Deployment notes

`HealthCheckMiddleware` answers `{BASE_PATH}health` before any other middleware. The Dockerfile's build-time collectstatic runs with `AUTH_PROVIDERS=local`. The runtime image has no `uv`, compilers or apt packages; the venv is `/opt/venv` (on `PATH`), so run `python manage.py ...`; the app runs from `/app` as the non-root `wagtail` user. Production env vars are documented in README.md.

## Conventions

- Code rules: `.claude/rules/code-quality.md` (clean, typed, Pythonic) and `.claude/rules/backend.md` (Django/Wagtail).
- `uv run invoke lint` must pass (ruff + mypy over `src/` and `tasks.py`).
