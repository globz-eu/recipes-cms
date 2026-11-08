# Spec: local login redirects to a cross-origin frontend

Issue: recipes-cms #35 (found while planning globz-eu/recipes-infrastructure#23).

## Problem

- Frontend "Username and password" link: `/admin/login/?next=<frontend url>`.
- Wagtail's `LoginView` (Django `LoginView`) follows `next` only to the request host;
  `success_url_allowed_hosts` is empty.
- Staging serves the frontend on `static.<app host>`, so users land on the Wagtail
  dashboard instead of the frontend.
- Social login and logout already accept extra hosts through
  `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` (`oidc_auth/redirects.py`).

## Goals

- Local login (`/admin/login/`) redirects to `next` when it points to the request host
  or an allowed redirect host; HTTPS required when the request is secure (same rule as
  `safe_redirect_url`).
- One neutral setting for all login/logout redirect hosts: `ALLOWED_REDIRECT_HOSTS`
  (user decision: the social name is confusing now that local login uses it too).
- Old name dropped everywhere, no fallback (user decision): recipes-infrastructure is
  changed at the same time.
- The recipes-infrastructure e2e check for this (`tests/e2e/reader-auth.spec.ts`,
  `test.fail(... "recipes-cms #35")`) passes on staging and loses its expected-failure
  marker.

## Non-goals

- No change to the frontend's login link or to the providers API.
- No change to which hosts are allowed (same values, new name).
- No custom login page; Wagtail's login form and template stay.

## Anti-goals

- Open redirect: any host outside request host + `ALLOWED_REDIRECT_HOSTS` must still
  fall back to the default (Wagtail dashboard).
- Plain-HTTP `next` accepted on a secure request.
- Social login losing its `next` check: python-social-auth reads
  `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` itself, so it must keep getting the same list.

## Design

### recipes-cms

- Settings: `ALLOWED_REDIRECT_HOSTS` replaces `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS`.
  - production: read from env var `ALLOWED_REDIRECT_HOSTS` (comma-separated); the old
    env var is no longer read.
  - dev: derived from `DEV_FRONTEND_ORIGINS` as today, under the new name.
  - No `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` alias (user decision at plan approval):
    python-social-auth falls back to the bare `ALLOWED_REDIRECT_HOSTS` setting.
- `safe_redirect_url` reads `ALLOWED_REDIRECT_HOSTS`.
- Local login: a `LoginView` subclass of Wagtail's, routed at `admin/login/` as
  `wagtailadmin_login` before `include(wagtailadmin_urls)` (like the logout override),
  whose `success_url_allowed_hosts` are the `ALLOWED_REDIRECT_HOSTS`.
- Docs: README, `.env.example`, CLAUDE.md use the new name.
- Tests: login with `next` to an allowed host redirects there; disallowed host and HTTP
  on a secure request fall back; existing redirect tests renamed to the new setting.

### recipes-infrastructure

- `src/app/productionEnv.ts`: set `ALLOWED_REDIRECT_HOSTS` instead of
  `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` (rename the related `urls` field to match);
  update unit tests and README.
- Remove the `test.fail(... "recipes-cms #35")` marker in
  `tests/e2e/reader-auth.spec.ts`.

## Constraints

- Deploy order: the infrastructure change only works with a recipes-cms image that
  reads `ALLOWED_REDIRECT_HOSTS`. Merge and tag recipes-cms first; deploy the
  infrastructure change together with the `containerImage` bump to that version.
  Deploying either alone loses the frontend host on staging.
- Tagging, bumping `containerImage` and deploying stay with the user.

## Left to the builder

- Where the defaults live (base vs. dev/production settings).
- Behaviour for an already signed-in user opening `/admin/login/?next=...`: follow
  whatever Wagtail's view does, with the same host check.
- Name of the renamed `urls` field in recipes-infrastructure.
