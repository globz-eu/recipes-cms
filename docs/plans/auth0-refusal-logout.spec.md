# Spec: sign refused Auth0 logins out of Auth0

Source: recipes-cms issue #47. A refused Auth0 login leaves the Auth0 session, so every retry is refused again.
Companion spec (message text only): recipes-frontend `docs/plans/email-unverified-message.spec.md`.

### Intent

- A refused Auth0 login ends the Auth0 session, so the next attempt shows Auth0's login page.
- An unverified user is told to verify, or to ask an admin to resend the verification email.

### Decided (user)

- Applies to every refused Auth0 login: `LoginRefused` and every other `AuthException` handled by `LoginRefusedMiddleware`.
- No resend from the CMS and no Auth0 Management API credential (`update:users` is too broad).
- Admins resend verification emails from the Auth0 dashboard.
- No recipes-infrastructure change.

### Non-goals / anti-goals

- No Zitadel change; no new `auth_error` codes; no Django session logout of a signed-in user (`already_signed_in`).
- Anti-goal: an open redirect, or losing the `auth_error` message.

### Behaviour

- `LoginRefusedMiddleware`: for an Auth0 failure, redirect through `auth0_logout_url` (`/v2/logout`, with `client_id`).
- Auth0 failure = the exception's backend, else `request.backend` / the `/complete/<backend>/` URL name.
- No backend identified, or another provider: today's redirect, no logout.
- Uniform: cancels, `access_denied`, state errors and `already_signed_in` also end the Auth0 session.

### returnTo

- Auth0 `/v2/logout` ignores query and hash when validating `returnTo`; the path must be registered.
- Registered (staging and dev, recipes-infrastructure `src/urls.ts`): `/admin/`, `/api/`, `/frontend/`.
- Frontend targets are always `/frontend/` (hash routing): `returnTo` = safe target + `auth_error=<code>`.
- Any other target (admin deep link, `/admin/login/`, DRF pages): `returnTo` = absolute `/admin/`, message via Django messages.
- `returnTo` is always absolute and built only from a `safe_redirect_url` target or the CMS's own `/admin/`.

### Message

- `EmailNotVerified.message`: "Please verify your email address with your provider. If you didn't get a verification email, ask an administrator to resend it."
- Same wording as the recipes-frontend `email_unverified` text.

### Done when

- `uv run invoke lint` and `uv run invoke test` pass.
- Tests cover each refusal kind for Auth0, both `returnTo` cases and an unchanged Zitadel redirect.
- Staging: the user toggles an Auth0 test user to unverified; the message shows and the next sign-in shows Auth0's login page.

### Left to the builder

- How the middleware is split (helpers, module boundaries).
