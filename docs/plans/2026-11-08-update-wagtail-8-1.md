# Plan: update Wagtail to 8.1 and refresh dependencies (recipes-cms #17)

Spec: `docs/plans/2026-11-08-update-wagtail-8-1.spec.md`.

## Context

- Wagtail 7.3 to 8.1, Django 6.0.2 to 6.1.3, all other locked packages refreshed.
- Wagtail 8.1 needs `django>=5.2`, DRF `>=3.18`, `django-ninja`, `django-tasks<0.13`.
- Release notes list no `INSTALLED_APPS`, setting or migration need for the new deps.
- Wagtail 8.0 removals do not hit us: no hooks, `INDEX`, tag settings, listing buttons.
- Django 6.1 removals do not hit us; `values_list(flat=True)` calls all name a field.
- Likely warning: `EMAIL_BACKEND` at `src/recipe_cms/settings/dev.py:13` (deprecated for `MAILERS`).
- Wagtail 8.1 redirects: auto-created only for live pages; `wagtail.contrib.redirects` is installed.
- Version text to update: `README.md:62` ("Wagtail 7.3"), `README.md:61`.

## Acceptance criteria

1. `uv.lock` resolves wagtail 8.1.x and Django 6.1.x; `pyproject.toml` bounds match.
2. `django>=6.1` is a direct dependency.
3. `uv run invoke lint` passes.
4. `uv run invoke test` and `uv run invoke test --postgres` pass.
5. `makemigrations --check` is clean; generated migrations are committed.
6. `python -Wd` test output shows no new warnings from `src/` or our settings.
7. Dev stack smoke test passes: admin login, recipe edit/publish, `/api/` list, bulk upload, media.
8. `uv run invoke dev --build` builds the image.

## Implementation steps

1. Increment 1, baseline: on `main` run lint and both test suites; record failures.
2. Branch `feature/update-wagtail-8-1`; run `uv lock --upgrade`; stop and report if a package blocks Wagtail 8.1 or Django 6.1.
   - Cap `social-auth-app-django>=5.7,<6` (user decision; 6.x is already POST-only); social-auth 6+ migration is a follow-up issue.
3. Increment 2: raise lower bounds in `pyproject.toml:8-23` to the locked versions, add `django>=6.1`; commit "Update dependencies".
4. Increment 3: run `makemigrations --check`; commit any generated migrations.
5. Replace `EMAIL_BACKEND` in `dev.py` with `MAILERS` (flagged by `-Wd`); commit.
   - Django 6.1: `LocalLoginView.get_success_url_allowed_hosts` takes `request`.
6. Increment 4: fix new ruff/mypy findings without silencing them; commit format-only changes separately.
7. Increment 5: update `README.md:61-62` versions and the Django comment in `base.py:4` only if misleading; commit "Update documented versions".

## Verification

- `uv run invoke lint`; `uv run invoke test`; `uv run invoke test --postgres`, then `uv run invoke down`.
- `(cd src && uv run python -Wd manage.py test)`; read output for warnings with stack in `src/`.
- Worktree only: `$DEV_STACK env --port <port>` first, then `uv run invoke dev --build`.
- Smoke test the spec's list at `localhost:<NGINX_HOST_PORT>`; provision Garage for media.
- Stop the watch process, then `uv run invoke down --volumes` (throwaway worktree) or without `--volumes`.

## Risks and open questions

- Decided (user): accept the new redirect behaviour; no `WAGTAILREDIRECTS_AUTO_CREATE` setting.
- Open: third-party deprecations are noted in the PR, not filtered, unless noisy.
- Risk: `django-tasks` may need a `TASKS` backend at runtime; confirm during the smoke test.
- Follow-up after merge, not a plan task: `uv run invoke bump --part minor` (0.14.0 to 0.15.0).
