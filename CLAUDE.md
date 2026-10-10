# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The app runs in Docker Compose (Postgres, Garage S3, nginx, Wagtail); tests and management commands run inside the `wagtail` container. Python deps are managed with `uv` (Python 3.14+). `.env` is required (copy `.env.example`).

**When testing against the dev environment, start it with `uv run invoke dev` (or `docker compose watch`), not plain `docker compose up -d`.** Only watch mode syncs `src/` into the container; otherwise the container runs stale code and tests silently run against old files.

```bash
uv run invoke dev [--build]        # docker compose up --watch (src/ is synced into the container)
uv run invoke test --label=recipes # run tests in the container (label optional)
uv run invoke format               # ruff check --fix + ruff format on src
uv run invoke bump --part minor    # bump version, commit, tag vX.Y.Z (tag push triggers the CI image build)

# Single test / module, directly
docker compose exec wagtail uv run manage.py test recipes.tests.test_bulk_upload
docker compose exec wagtail uv run manage.py test recipes.tests.test_bulk_upload.SomeTest.test_name

docker compose exec wagtail uv run manage.py migrate
docker compose exec wagtail uv run manage.py import_recipes recipes.json
```

`manage.py` lives in `src/`. Settings are `recipe_cms.settings.{dev,production}` (both extend `base`); the dev settings are baked in via a Docker build arg.

## Architecture

Django + Wagtail headless CMS: Wagtail admin for editors, DRF API under `/api/` consumed by a separate frontend (`../recipes-frontend`, served by nginx at `/frontend/` locally and cross-origin with credentials in production, hence CORS/CSRF settings and the `/api/csrf/` endpoint).

- **`auth0_auth`**: Auth0 OpenID Connect via social-auth; the pipeline puts new users in the Wagtail "Editors" group. Custom logout view.
- **`home`**: `HomePage` (one per locale) is the only allowed parent of `RecipePage`. `locales.get_requested_locale` implements the `?locale=` query parameter (default `en`) shared by the API views. Also holds the `ensure_admin` command and the shared permission class.
- **`recipes`**: `RecipePage` with orderable `RecipeIngredient` children (modelcluster `ParentalKey`). Bulk upload is split across `serializers.py` (validation), `importer.py` (service, shared by the API view and the `import_recipes` command) and `views.py`.
- **`image_auth`**: `serve_media` view; nginx proxies `/media/` to it so media is only streamed to authorized users from S3 (django-storages + wagtail-storages).

### Multilingual model

Wagtail i18n is enabled with `en` (default), `de`, `fr`, `nl`. Each locale has its own HomePage tree (depth 2); each translation of a recipe lives under its locale's HomePage and translations are linked via a shared `translation_key`. Locales and translated homepages are created by data migrations (`home/migrations/0002`, `0004`, `0005`), so tests and the importer rely on those homepages existing.

### Bulk import semantics (`recipes/importer.py`)

- Recipes are matched by `(slug, locale)`; existing pages are fully overwritten (including the ingredient list), new ones created under the locale's HomePage.
- All-or-nothing: an outer `transaction.atomic()` wraps per-group savepoints; errors are collected per group index and the outer transaction is rolled back, raising `RecipeImportError`.
- Permissions follow Wagtail page permissions when a user is given (API); users who can't publish leave a draft revision. The management command passes no user and skips permission checks.
- Edits go through `save_revision` then `publish`/`unpublish` rather than direct saves, so Wagtail revision history stays intact.

### Deployment notes

Staging runs on Scaleway, managed by the sibling `recipes-infrastructure` Pulumi project; production-only env vars (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `STATIC_BUCKET_NAME`, …) are documented in README.md. Images are built by GitHub Actions on `vX.Y.Z` tags. The `HealthCheckMiddleware` answers `{BASE_PATH}health` before any other middleware.

## Conventions

- Ruff: line length 88, double quotes, import sorting enabled (`I`).
- Tests live in `<app>/tests/` and use Django's test runner (not pytest).
