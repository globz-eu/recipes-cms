# Plan: local login redirects to a cross-origin frontend

Spec: [2026-11-08-local-login-redirect-hosts.spec.md](2026-11-08-local-login-redirect-hosts.spec.md).
Issue: recipes-cms #35.

## Context and goal

- `/admin/login/?next=<frontend>` ignores `next` off the request host.
- Cause: Django `RedirectURLMixin.success_url_allowed_hosts = set()` (`django/contrib/auth/views.py:38`).
- Goal: local login honours `ALLOWED_REDIRECT_HOSTS`, the one renamed redirect-host setting.
- recipes-infrastructure sets the new env var; its e2e expected-failure marker goes.
- Base both repos on `origin/main`; recipes-infrastructure refs checked against it.

## Confirmed library behaviour (Django 6.0.2, Wagtail 7.3, social-auth-core 4.8.5)

- `get_success_url_allowed_hosts()` returns request host plus `success_url_allowed_hosts`.
- `get_redirect_url()` passes `require_https=request.is_secure()`: secure requests refuse `http://` targets.
- Wagtail `account.LoginView.get_success_url`: safe `next`, else `reverse("wagtailadmin_home")`.
- Wagtail `LoginView.get`: signed-in user with `wagtailadmin.access_admin` is redirected via `get_success_url`.
- Signed-in users without admin access get the form again (unchanged).
- Wagtail routes `login/` as `wagtailadmin_login` (`wagtail/admin/urls/__init__.py:144`).
- social-core reads `backend.setting("ALLOWED_REDIRECT_HOSTS")` (`social_core/actions.py:40,145,184`).
- Lookup order: `SOCIAL_AUTH_<BACKEND>_…`, `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS`, then bare `ALLOWED_REDIRECT_HOSTS` (`social_core/strategy.py:70`).

## Acceptance criteria

1. POST `/admin/login/` with `next` on an `ALLOWED_REDIRECT_HOSTS` host redirects there.
2. `next` on any other host redirects to `wagtailadmin_home`.
3. `http://` `next` on a secure request redirects to `wagtailadmin_home`.
4. Signed-in admin GET `/admin/login/?next=<allowed>` redirects to `next`.
5. `resolve("/admin/login/")` hits the new view; login template and social buttons unchanged.
6. Production reads env `ALLOWED_REDIRECT_HOSTS`; env `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` is ignored.
7. Dev derives `ALLOWED_REDIRECT_HOSTS` from `DEV_FRONTEND_ORIGINS`; social login keeps accepting them.
8. No `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` anywhere; social-core uses its bare-name fallback.
9. recipes-infrastructure sets `ALLOWED_REDIRECT_HOSTS`; unit tests, lint, typecheck pass.
10. After deploy, `tests/e2e/reader-auth.spec.ts` passes on staging without `test.fail`.

## Design: recipes-cms

- `src/recipe_cms/settings/base.py`: `ALLOWED_REDIRECT_HOSTS: list[str] = []`, comment naming social-core's fallback.
- `settings/dev.py:31` and `settings/production.py:27`: set `ALLOWED_REDIRECT_HOSTS` (no alias; user decision).
- `src/oidc_auth/redirects.py:17,25`: read `settings.ALLOWED_REDIRECT_HOSTS`.
- `src/oidc_auth/views.py`: `LocalLoginView(wagtail.admin.views.account.LoginView)`.
- It overrides `get_success_url_allowed_hosts()`; reads settings per request, so `override_settings` works.
- `src/recipe_cms/urls.py:19`: route `admin/login/` as `wagtailadmin_login` before `include(wagtailadmin_urls)`.
- Rejected: class attribute (frozen at import); custom `get_redirect_url` (duplicates Django's check).

## Design: recipes-infrastructure

- `src/urls.ts:47,109`: rename `socialAuthRedirectHosts` to `allowedRedirectHosts`.
- `src/app/productionEnv.ts:66`: set `plainEnv.ALLOWED_REDIRECT_HOSTS`.
- `tests/unit/urls.test.ts:65`, `tests/unit/program-staging-container.test.ts:40`: new names.
- README has no old-name hit; drop the "Known failure" paragraph (`README.md:565-569`).
- `tests/e2e/reader-auth.spec.ts:42-43`: drop the #35 comment and `test.fail` line.
- `tests/e2e/support/login.ts:11,24-27`: drop the #35 workaround in `signInThroughFrontend` and its comments.

## Implementation steps: recipes-cms

- Worktree off `origin/main`: branch `feature/local-login-redirect-hosts` in `../recipes-cms-worktrees/feature-local-login-redirect-hosts`.
- Commit 1 (`refactor(settings)`): rename setting, `redirects.py`, existing tests.
- Rename overrides in `oidc_auth/tests/test_views.py:183,197,215,246` and `test_middleware.py:21`.
- `home/tests/test_dev_frontend_origins.py`: assert the new name in dev and production; old name absent.
- Production test: set both env vars; old one must not leak into the setting.
- Add a test: social-core `backend.setting("ALLOWED_REDIRECT_HOSTS")` returns the new setting.
- Commit 2 (`fix(oidc_auth)`): `LocalLoginView`, URL, new `oidc_auth/tests/test_local_login.py`.
- New tests: criteria 1-5; pin `AUTH_PROVIDERS`/`AUTHENTICATION_BACKENDS` like recipes-cms commit `fa6983d`.
- Commit 3 (`docs`): `README.md` (3 hits), `CLAUDE.md` nginx bullet (also name `LocalLoginView`); `git grep` the old name.
- recipes-cms `main` has no `.env.example` (it moved to recipes-infrastructure `dev/.env.example`, no hit).

## Verification: recipes-cms

- Tests run on the host with SQLite: `uv run invoke test 2>&1 | cat` (no stack needed).
- `uv run invoke format 2>&1 | cat`; `uv run invoke lint 2>&1 | cat` (ruff + mypy).
- No dev stack; the staging e2e check verifies the redirect end to end after deploy.
- recipes-cms PR says `Part of #35`; user merges and tags (`uv run invoke bump`).

## Implementation steps: recipes-infrastructure

- Same branch name off `origin/main`, worktree `../recipes-infrastructure-worktrees/feature-local-login-redirect-hosts`.
- Commit 1 (`refactor`): field rename, env var, unit tests.
- Commit 2 (`test(e2e)`): remove the `test.fail` marker, helper workaround, README paragraph.
- PR says `Closes globz-eu/recipes-cms#35` (merged last); #23 is closed, so not linked.
- `containerImage` bump: user adds it to this PR after tagging recipes-cms (user decision).
- Verify: `npm run lint`, `npm run typecheck`, `npm run test:unit`.
- After deploy (`scripts/deploy-staging.sh`, user): run the e2e suite per `origin/main` README.

## Deploy-order constraint

- recipes-cms first: merge, tag, image built by CI.
- Deploy infra rename together with `containerImage` bump; never either alone.
- Old image plus new env var, or new image plus old env var: frontend host lost.
- Tagging, bumping and deploying stay with the user.

## Risks

- A leftover `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` would shadow the new name for social-core.
- Open redirect if `get_success_url_allowed_hosts` drops the request-host check; covered by criterion 2.

## Decisions (user, at plan approval)

- Alias dropped: social-core falls back to bare `ALLOWED_REDIRECT_HOSTS` (`social_core/strategy.py:70`).
- `containerImage` bump added by the user to the recipes-infrastructure PR after tagging.
