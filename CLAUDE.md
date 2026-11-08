# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@~/.claude/architectures/recipes.md

The import above is the shared recipes architecture file; it resolves only if `~/.claude/architectures/recipes.md` is a symlink to `architectures/recipes.md` in the sibling recipes-roadmap repo (`ln -s "$PWD/../recipes-roadmap/architectures/recipes.md" ~/.claude/architectures/recipes.md`, after `mkdir -p ~/.claude/architectures`). Without it, Claude Code skips the import.

## Commands

The dev stack (Postgres, Garage S3, nginx, Wagtail, frontend release) is defined in the sibling repo recipes-infrastructure (`dev/compose.yml`, driven by `scripts/dev-stack.sh`; see its README, "Local dev environment"). This repo only adds `compose.dev.yml`, which builds this checkout and syncs `src/` into the `wagtail` container. Clone recipes-infrastructure next to this repo, or set `RECIPES_INFRA_DIR` (shell or `.env`) to its checkout. Python deps are managed with `uv` (Python 3.14+). `.env` is required for the stack: in the main checkout run `cp ../recipes-infrastructure/dev/.env.example .env && chmod 600 .env` and fill in the secrets (`dev-stack.sh env` is only for extra worktrees). `RECIPES_INFRA_DIR` in `.env` only helps once `.env` exists; use the shell for the first setup. The tests do not need it. This requires recipes-infrastructure PR #22 (adds `scripts/dev-stack.sh` and `dev/compose.yml`), which is still open: until it is merged, `dev-stack.sh` exists only on its branch `feature/dev-environment`, so check that branch out, or `invoke dev`, `down` and `test --postgres` fail. No release tag exists yet; once PR #22 is merged use `main`, and replace it with the tag once one exists.

**Tests run on the host with SQLite by default** (`uv run invoke test`, no Docker, no `.env`). `uv run invoke test --postgres` runs them in a one-off `wagtail` container of the dev stack against Postgres; use it for Postgres-specific behaviour. Changes touching email uniqueness (the `LOWER(email)` index, `oidc_auth` migration 0001, `enforce_email_ownership`, user forms) or other Postgres-specific behaviour must be verified with `uv run invoke test --postgres`, because CI runs only lint and the SQLite tests (on every push) and the index test is skipped on SQLite.

**When testing against the dev environment, start it with `uv run invoke dev`, not plain `docker compose up -d`.** Only watch mode syncs `src/` into the container; otherwise the container runs stale code and tests silently run against old files. Other compose commands: `$DEV_STACK compose ARGS` (`DEV_STACK="${RECIPES_INFRA_DIR:-<main checkout>/../recipes-infrastructure}"/scripts/dev-stack.sh`; `../recipes-infrastructure` does not resolve from a worktree; the `invoke` tasks resolve it themselves) (run from this directory, it identifies the stack).

**One stack per git worktree, so branches can be tested in parallel.** In an extra worktree run `$DEV_STACK env --port 8081` (writes its `.env` from the main worktree's with a unique project name, ports, cookie names and `DEV_FRONTEND_ORIGINS`; options and port rules are in the recipes-infrastructure README, "Parallel stacks (git worktrees)"), then `uv run invoke dev`. Only nginx and postgres are published; use `localhost:<NGINX_HOST_PORT>`. Each stack has an empty Garage: provision it via `dev-stack.sh compose` (recipes-cms README, "Provisioning Garage"). **Whoever starts a stack stops it:** stop the watch process, then `uv run invoke down` (`--volumes` for throwaway worktrees, before deleting them; `invoke test --postgres` also leaves the database container running, so run `invoke down` afterwards).

```bash
uv run invoke dev [--build]         # dev-stack.sh up --watch --skip-lookup CMS_VERSION -f compose.dev.yml (src/ is synced)
uv run invoke down [--volumes]      # dev-stack.sh down [-v]
uv run invoke test --label=recipes  # run tests on the host with SQLite (label optional); --postgres: in the container
uv run invoke format                # ruff check --fix + ruff format on src and tasks.py
uv run invoke lint                  # ruff check + ruff format --check + mypy (on the host, changes nothing)
uv run invoke bump --part minor     # bump version, commit, tag vX.Y.Z (tag push triggers the CI image build)

# Single test / module, directly on the host (SQLite)
(cd src && uv run manage.py test recipes.tests.test_bulk_upload)
(cd src && uv run manage.py test recipes.tests.test_bulk_upload.SomeTest.test_name)

# Management commands in the running stack (DEV_STACK as above)
$DEV_STACK compose exec wagtail uv run manage.py migrate
$DEV_STACK compose exec wagtail uv run manage.py import_recipes recipes.json
```

`manage.py` lives in `src/`. Settings are `recipe_cms.settings.{dev,production}` (both extend `base`); the dev settings are baked in via a Docker build arg.

## Architecture

Django + Wagtail headless CMS: Wagtail admin for editors, DRF API under `/api/` consumed by a separate frontend (`../recipes-frontend`; the dev stack downloads its latest release and nginx serves it at `/frontend/` locally, while `npm run dev` there can use this backend through the nginx proxy; it is cross-origin with credentials in production, hence CORS/CSRF settings and the `/api/csrf/` endpoint).

- **`oidc_auth`**: pluggable sign-in; `AUTH_PROVIDERS` (`local`, `auth0`, `zitadel`; default `local,auth0`) selects the methods, and settings fail at import if an enabled provider's variables are missing or blank (`config.py`; zitadel also needs `ZITADEL_ROLE_ORG_ID`, and `read_zitadel_roles` only keeps roles granted in that org). `ZitadelOpenIdConnect.get_scope()` adds `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>` (Zitadel then uses that org's login policy and admits only its users) and `urn:zitadel:iam:user:resourceowner`. Social-auth pipeline: `enforce_zitadel_org` (right after `auth_allowed`; fails closed: a Zitadel login whose `urn:zitadel:iam:user:resourceowner:id` claim is missing or differs from `ZITADEL_ROLE_ORG_ID` is refused with `OrgMismatch`), `enforce_email_ownership` (one email, one provider; verified email required; refusals are `LoginRefused` turned into a redirect with `auth_error=email_missing|email_unverified|email_in_use|already_signed_in|org_mismatch|login_failed` by `LoginRefusedMiddleware`, which also maps any other social-auth failure to `login_failed`; `pipeline.create_user` wraps the default so a lost race on the unique index becomes `email_in_use`) and `sync_roles` (provider-specific role readers in `providers.py` mapped through `ROLE_GROUP_MAP`; `admin` grants superuser/staff). `CustomLogoutView` logs out through the user's own provider; `LocalLoginView` (Wagtail's login at `admin/login/`) also follows `next` to `ALLOWED_REDIRECT_HOSTS` (the setting social-core and `safe_redirect_url` read too; HTTPS required on secure requests); `GET /api/auth/providers/` lists the enabled methods for the frontend. Without `local`, `PermissionsOnlyBackend` replaces `ModelBackend` (permissions still need it). Migration `0001` adds a unique `LOWER(email)` index (blank excepted). Local user forms and `ensure_users`/`ensure_admin` refuse any duplicate email (case-insensitive); the edit form drops password fields for social users and the commands refuse a username belonging to a social user; `WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False`. The Dockerfile's build-time collectstatic runs with `AUTH_PROVIDERS=local`.
- **`home`**: `HomePage` (one per locale) is the only allowed parent of `RecipePage`. `locales.get_requested_locale` implements the `?locale=` query parameter (default `en`) shared by the API views. Also holds the `ensure_admin` command (deployments), the `ensure_users` command (local superuser/editor/moderator from `DJANGO_*` env vars, run by compose on start), the `/api/dev-login/` view (404 unless `DEV_PASSWORD_LOGIN`, which only `settings/dev.py` sets) and the shared permission class.
- **`recipes`**: `RecipePage` with orderable `RecipeIngredient` children (modelcluster `ParentalKey`). Bulk upload is split across `serializers.py` (validation), `importer.py` (service, shared by the API view and the `import_recipes` command) and `views.py`.
- **nginx**: its config lives in recipes-infrastructure (`dev/config/nginx/`), not here; see that README for the `X-Forwarded-Host $host:<published port>` rule (never `$http_host`). On this side, dev settings read `SESSION_COOKIE_NAME`/`CSRF_COOKIE_NAME` from env, and `DEV_FRONTEND_ORIGINS` (comma-separated, default `http://localhost:5173`) for `CSRF_TRUSTED_ORIGINS` and, as `host:port`, `ALLOWED_REDIRECT_HOSTS`: the Vite proxy keeps the browser's `Origin`, so Django sees a cross-origin request.
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

- Code rules are in `.claude/rules/code-quality.md` (clean, typed, Pythonic code) and `.claude/rules/backend.md` (Django/Wagtail).
- Ruff: line length 88, double quotes, import sorting, plus Pythonic rule sets, `C901` complexity and `ANN` annotations in production code; mypy with django-stubs checks `src/` and `tasks.py`. `uv run invoke lint` must pass.
- Commits: capitalised imperative verb, short, no prefix; small, granular commits.
- Tests live in `<app>/tests/` and use Django's test runner (not pytest).
