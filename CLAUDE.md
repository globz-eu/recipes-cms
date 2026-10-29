# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@~/.claude/architectures/recipes.md

The import above is the shared recipes architecture file; it resolves only if `~/.claude/architectures/recipes.md` is a symlink to `architectures/recipes.md` in the sibling recipes-roadmap repo (`ln -s "$PWD/../recipes-roadmap/architectures/recipes.md" ~/.claude/architectures/recipes.md`, after `mkdir -p ~/.claude/architectures`). Without it, Claude Code skips the import.

## Commands

The app runs in Docker Compose (Postgres, Garage S3, nginx, Wagtail); tests and management commands run inside the `wagtail` container. Python deps are managed with `uv` (Python 3.14+). `.env` is required (copy `.env.example`).

**When testing against the dev environment, start it with `uv run invoke dev` (or `docker compose watch`), not plain `docker compose up -d`.** Only watch mode syncs `src/` into the container; otherwise the container runs stale code and tests silently run against old files.

**One stack per git worktree, so branches can be tested in parallel.** In an extra worktree run `uv run invoke worktree-env --port 8081` (writes its `.env` from the main worktree's with a unique `COMPOSE_PROJECT_NAME`, `NGINX_HOST_PORT`, `POSTGRES_HOST_PORT` and cookie names), then `uv run invoke dev`. Only nginx and postgres are published; wagtail and Garage are internal, so use `localhost:<NGINX_HOST_PORT>`. `S3_CUSTOM_DOMAIN` and `WAGTAILADMIN_BASE_URL` derive from the port unless set in `.env` (drop them from a copied `.env`). Social login and the frontend's Vite proxy only work on 8080. **Whoever starts a stack stops it:** stop the watch process, then `uv run invoke down` (`--volumes` for throwaway worktrees, before removing them).

```bash
uv run invoke dev [--build]         # docker compose up --watch (src/ is synced into the container)
uv run invoke down [--volumes]      # docker compose down [-v]
uv run invoke worktree-env --port N  # write this worktree's .env (own project name, ports, cookies)
uv run invoke test --label=recipes  # run tests in the container (label optional)
uv run invoke format                # ruff check --fix + ruff format on src
uv run invoke bump --part minor     # bump version, commit, tag vX.Y.Z (tag push triggers the CI image build)

# Single test / module, directly
docker compose exec wagtail uv run manage.py test recipes.tests.test_bulk_upload
docker compose exec wagtail uv run manage.py test recipes.tests.test_bulk_upload.SomeTest.test_name

docker compose exec wagtail uv run manage.py migrate
docker compose exec wagtail uv run manage.py import_recipes recipes.json
```

`manage.py` lives in `src/`. Settings are `recipe_cms.settings.{dev,production}` (both extend `base`); the dev settings are baked in via a Docker build arg.

## Architecture

Django + Wagtail headless CMS: Wagtail admin for editors, DRF API under `/api/` consumed by a separate frontend (`../recipes-frontend`; compose downloads its latest release via the one-shot `frontend` service and nginx serves it at `/frontend/` locally, while `npm run dev` there can use this backend through the nginx proxy; it is cross-origin with credentials in production, hence CORS/CSRF settings and the `/api/csrf/` endpoint).

- **`oidc_auth`**: pluggable sign-in; `AUTH_PROVIDERS` (`local`, `auth0`, `zitadel`; default `local,auth0`) selects the methods, and settings fail at import if an enabled provider's variables are missing (`config.py`). Social-auth pipeline: `enforce_email_ownership` (one email, one provider; verified email required; refusals are `LoginRefused` turned into a redirect with `auth_error=email_missing|email_unverified|email_in_use|already_signed_in|login_failed` by `LoginRefusedMiddleware`, which also maps any other social-auth failure to `login_failed`; `pipeline.create_user` wraps the default so a lost race on the unique index becomes `email_in_use`) and `sync_roles` (provider-specific role readers in `providers.py` mapped through `ROLE_GROUP_MAP`; `admin` grants superuser/staff). `CustomLogoutView` logs out through the user's own provider; `GET /api/auth/providers/` lists the enabled methods for the frontend. Without `local`, `PermissionsOnlyBackend` replaces `ModelBackend` (permissions still need it). Migration `0001` adds a unique `LOWER(email)` index (blank excepted). Local user forms and `ensure_users`/`ensure_admin` refuse any duplicate email (case-insensitive); the edit form drops password fields for social users and the commands refuse a username belonging to a social user; `WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False`. The Dockerfile's build-time collectstatic runs with `AUTH_PROVIDERS=local`.
- **`home`**: `HomePage` (one per locale) is the only allowed parent of `RecipePage`. `locales.get_requested_locale` implements the `?locale=` query parameter (default `en`) shared by the API views. Also holds the `ensure_admin` command (deployments), the `ensure_users` command (local superuser/editor/moderator from `DJANGO_*` env vars, run by compose on start), the `/api/dev-login/` view (404 unless `DEV_PASSWORD_LOGIN`, which only `settings/dev.py` sets) and the shared permission class.
- **`recipes`**: `RecipePage` with orderable `RecipeIngredient` children (modelcluster `ParentalKey`). Bulk upload is split across `serializers.py` (validation), `importer.py` (service, shared by the API view and the `import_recipes` command) and `views.py`.
- **nginx**: `config/nginx/nginx.conf.template` is rendered by the image entrypoint (envsubst, filtered to `NGINX_HOST_PORT`) and sends `X-Forwarded-Host $host:<published port>`; `$server_port` would be the container port. Do not switch it to `$http_host`: the Vite proxy sends `localhost:5173` and social-login callbacks are registered for `localhost:8080`. Dev settings read `SESSION_COOKIE_NAME`/`CSRF_COOKIE_NAME` from env.
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
