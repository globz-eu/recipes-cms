# Spec: Auth0 OIDC discovery without double slash (recipes-cms #42)

Auth0 login start returns 500 on staging: Auth0 now 404s `https://<DOMAIN>//.well-known/openid-configuration`.

## Cause

- social-core `Auth0OpenIdConnectAuth.oidc_endpoint()` returns `https://<DOMAIN>/` (trailing slash).
- `OpenIdConnectAuth.oidc_config()` appends `/.well-known/openid-configuration`.
- Same in social-core 4.8.5 and 4.9.1; Auth0 changed, not our upgrade.

## Goals

- Discovery requests `https://<DOMAIN>/.well-known/openid-configuration`.
- `GET /login/auth0_openidconnect/` redirects (302) to the Auth0 authorize endpoint again.
- Regression test that fails on the current code (discovery URL has no `//`).
- Backend name stays `auth0_openidconnect`: login URLs, callback URL and `UserSocialAuth.provider` rows unchanged.
- Release v0.15.1 after the user merges (`invoke bump --part patch`); pin it in recipes-infrastructure PR #29 and redeploy staging.

## Non-goals

- social-auth upgrade (#39).
- Hard-coding Auth0 endpoint URLs in settings.

## Calls made by Claude

- Subclass `Auth0OpenIdConnectAuth` in `oidc_auth/backends.py` with `oidc_endpoint()` = `https://{DOMAIN}`, like `ZitadelOpenIdConnect`.
- Point `SOCIAL_BACKENDS[AUTH0]` (`oidc_auth/config.py`) to it.
- ID token issuer still comes from discovery (`issuer` = `https://<DOMAIN>/`), so token validation is unchanged.

## Left to the builder

- Test placement (`test_backends.py` and/or `test_login_flow.py`).
