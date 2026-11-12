# Plan: sign refused Auth0 logins out of Auth0 (recipes-cms #47)

Spec (binding): `docs/plans/auth0-refusal-logout.spec.md`.

## Goal

- Every Auth0 login refused by `LoginRefusedMiddleware` redirects through Auth0 `/v2/logout`.
- The next attempt shows Auth0's login page instead of an instant SSO refusal.
- `EmailNotVerified.message` tells the user to verify or ask an admin to resend.

## Files

- `src/oidc_auth/providers.py`: extract a `return_to`-only Auth0 logout URL builder.
- `src/oidc_auth/middleware.py`: backend detection, `returnTo` choice, Auth0 redirect.
- `src/oidc_auth/exceptions.py:21`: new `EmailNotVerified.message`.
- Tests: `src/oidc_auth/tests/test_middleware.py`, `test_login_flow.py`, provider test module.
- Docs: `CLAUDE.md` (`oidc_auth` bullet), `README.md:412` "Refused logins".

## Implementation steps

Increment 1: message
1. Set `EmailNotVerified.message` to the spec text, verbatim (spec "Message").

Increment 2: logout URL builder
2. Add `auth0_logout_endpoint(return_to: str) -> str` in `providers.py`; no request or social link.
3. `auth0_logout_url` (`providers.py:63`) delegates to it; `Provider` signature unchanged.

Increment 3: middleware
4. `_failed_backend_name(request, exception) -> str | None`: `exception.backend.name` if `str`.
5. Else `request.backend.name`, else `request.resolver_match` `social:complete` kwarg `backend`.
6. `_is_auth0(name)`: equals `PROVIDERS[AUTH0].backend_name` and `AUTH0 in settings.AUTH_PROVIDERS`.
7. `_auth0_return_to(request, target, code, message)`: safe target with path `/frontend/` → absolute target + `auth_error`.
8. Any other or missing target: `messages.error`, return `build_absolute_uri(reverse("wagtailadmin_home"))`.
9. `process_exception`: Auth0 → redirect to `auth0_logout_endpoint(return_to)`; else today's branch unchanged.
10. Use `_failed_backend_name` in the log lines too (replaces the `"unknown"` lookup).

Increment 4: docs
11. Update the `CLAUDE.md` `oidc_auth` bullet and README "Refused logins" with the Auth0 logout.

## Tests

- Providers: `auth0_logout_endpoint` builds `https://<domain>/v2/logout?client_id=…&returnTo=…`.
- Middleware, Auth0 backend: `LoginRefused`, `identity_in_use`, `AuthCanceled`, `AuthSessionError`, `AuthCredentialError` each log out.
- `returnTo` with `next=/frontend/?locale=de` keeps the query, adds `auth_error`, is absolute.
- `returnTo` is the absolute `/admin/` for `/admin/pages/`, `/admin/login/`, a disallowed host or no `next`.
- The `/admin/` case stores the message; the frontend case does not.
- Backend detected via `request.backend` and via `/complete/auth0_openidconnect/` when `exception.backend` is a `Mock`.
- Zitadel, unknown backend and Auth0 not enabled keep today's `Location`; existing tests stay green.
- Login flow: unverified Auth0 claims through `/complete/auth0_openidconnect/` end at Auth0 logout.

## Acceptance criteria

1. Every `AuthException` from an Auth0 login redirects to `https://<AUTH0 domain>/v2/logout` with `client_id`.
2. `returnTo` is absolute; path is `/frontend/` (plus `auth_error=<code>`) or `/admin/`.
3. `returnTo` never contains a host rejected by `safe_redirect_url`.
4. The `/admin/` case shows the refusal message after Auth0 returns.
5. Zitadel and unidentified-backend refusals redirect exactly as before.
6. `email_unverified` message matches the spec text.
7. `uv run invoke lint` and `uv run invoke test` pass.
8. Staging check by the user: unverified Auth0 user sees the message; next sign-in shows Auth0's login page.

## Risks and open questions

- Risk: a safe `/frontend/` target on a host not in `auth0LogoutUrls` makes Auth0 show an error.
- Covered by the spec's statement that staging and dev register every `/frontend/` origin.
- No open questions.
