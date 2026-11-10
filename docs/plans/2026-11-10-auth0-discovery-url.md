# Plan: Auth0 discovery URL without double slash (recipes-cms #42)

Spec: `docs/plans/2026-11-10-auth0-discovery-url.spec.md`.

## Context

- Upstream `oidc_endpoint()` returns `api_path("")` = `https://<DOMAIN>/` (`social_core/backends/auth0_openidconnect.py:24`).
- `oidc_config()` appends `/.well-known/openid-configuration` (`open_id_connect.py:159`).
- Nothing else in social-core calls `oidc_endpoint()` or `api_path()`.
- Issuer, JWKS and endpoints come from discovery (`get_setting_config`); unaffected.
- `oidc_config` is `@cache`d per class, process-wide; tests must call `oidc_config.invalidate()`.
- Old class path in `config.py:17`, `test_config.py:13`, `test_local_login.py:88`, `test_dev_frontend_origins.py:111`.
- `providers.py:113` and logout use backend name `auth0_openidconnect`; unchanged.

## Acceptance criteria

1. `Auth0OpenIdConnect.oidc_endpoint()` returns `https://<DOMAIN>` without trailing slash.
2. `oidc_config()` requests `https://<DOMAIN>/.well-known/openid-configuration` (no `//`).
3. `GET /login/auth0_openidconnect/` returns 302 to the discovered `authorization_endpoint`.
4. Backend name stays `auth0_openidconnect`; login, callback and logout URLs unchanged.
5. `SOCIAL_BACKENDS[AUTH0]` is `oidc_auth.backends.Auth0OpenIdConnect`.
6. Tests for 1–3 fail on current `main` of recipes-cms.

## Implementation steps

1. Add `Auth0OpenIdConnect(Auth0OpenIdConnectAuth)` in `oidc_auth/backends.py`; override `oidc_endpoint()` only.
2. Docstring: why (upstream trailing slash, Auth0 404s `//`).
3. Point `config.py:17` to it; update `test_config.py:13`.
4. Replace the hard-coded path in `test_local_login.py:88`, `test_dev_frontend_origins.py:111` with `SOCIAL_BACKENDS[AUTH0]`.
5. `test_backends.py`: name, `oidc_endpoint()`, and `oidc_config()` with `patch.object(..., "get_json")` asserting the URL.
6. `test_login_flow.py`: Auth0 login start with patched `get_json`; assert URL and 302 target.
7. Invalidate `oidc_config` cache in `setUp` and `addCleanup` of both tests.
8. Commit: "Fix Auth0 discovery URL double slash".

## Verification

- `uv run invoke format`, `uv run invoke lint`.
- `uv run invoke test` (SQLite); Postgres not needed (no email uniqueness change).
- Check new tests fail with `config.py:17` reverted.

## Risks and open questions

- Django drops sessions whose `_auth_user_backend` left `AUTHENTICATION_BACKENDS`. Decided (user): accepted.
- Existing Auth0 sessions on staging get logged out once after deploy; accepted? Decided (user): accepted.
- Upstream fix may land with #39; then drop the subclass.
