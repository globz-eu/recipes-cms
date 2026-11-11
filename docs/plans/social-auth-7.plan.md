# Plan: upgrade social-auth-app-django to 7.2 (recipes-cms #39)

Spec: `docs/plans/social-auth-7.spec.md` (user-approved). Frontend half: recipes-frontend `docs/plans/login-post-form.spec.md`.

## Context and goal

- `pyproject.toml:13` caps `social-auth-app-django>=5.7,<6`; `uv.lock` has app 5.9.0, core 4.9.1.
- Target: `social-auth-app-django>=7.2,<8`, which pins `social-auth-core>=6.2.0,<7.0.0` (app 7.2.0 `pyproject.toml`).
- Same buttons, redirects and `auth_error` codes; existing Auth0/Zitadel users keep their accounts.

## Library facts (sources)

- `social_django/views.py` 7.2.0: `auth` is `@require_POST`; CSRF comes from our global `CsrfViewMiddleware`.
- `complete` stays `@csrf_exempt` and accepts GET callbacks.
- app CHANGELOG 6.0.0: `SOCIAL_AUTH_REQUIRE_POST` removed, login views always POST.
- 6.1.0 adds `app-launch/` / `idp-launch/` GET bridges; not used here (spec: no redirect view).
- core `social_core/exceptions.py` 6.2.0: `AuthAlreadyAssociated`, `AuthForbidden`, `AuthStateMissing`, `AuthTokenError` are gone, no aliases.
- New classes: `AuthAssociationError` (`identity_in_use`), `AuthPolicyError` (`authentication_disallowed`), `AuthCanceled` (kept), `AuthSessionError`, `AuthCredentialError`, `AuthResponseError`, `AuthProviderError`.
- `SocialAuthBaseException.__init__(backend=None, *details, code=None, ...)` sets `self.code = code or self.default_code`.
- Consequence: the instance `code` shadows our `LoginRefused.code` class attribute (`oidc_auth/exceptions.py:9`), which then reads `unknown_error`.
- `default_code` must be a `REASONS` key (eager `REASONS[self.default_code]`), so `org_mismatch` cannot be one.
- app `storage.py` 7.2.0 `create_user`: `IntegrityError` becomes `AuthAssociationError(code="username_in_use"|"email_in_use")` only for recognised constraints.
- Recognition is by constraint name (Postgres `diag.constraint_name`) or exact SQLite message; our `LOWER(email)` index is not recognised.
- So a lost email race now raises a raw `IntegrityError` from `social_create_user`.
- core `backends/base.py` 6.2.0 `run_pipeline` does `out.pop("request", None)`; use `strategy.request` (app CHANGELOG 7.0.0).
- Our steps in `oidc_auth/pipeline.py` take no `request`; nothing to change, only verify.
- core CHANGELOG 6.0.0: custom pipelines must add `social_core.pipeline.social_auth.social_names` right after `social_details` (`DEFAULT_AUTH_PIPELINE` 6.2.0).

## Library facts: `id_key` and legacy uids

- app migration `0018_usersocialauth_id_key` adds `id_key` (default `""`); `0020_backfill_id_keys` fills it.
- `0020` uses a hard-coded `OLD_ID_KEYS` merged with `SOCIAL_AUTH_OLD_ID_KEYS`; it loads no backends and checks no evidence.
- `OLD_ID_KEYS` has `"auth0_openidconnect": "sub"` but no `"zitadel"`; Zitadel rows stay `id_key=""` without our setting.
- `0020` reverse is `RunPython.noop` and `atomic = False`.
- core `pipeline/social_auth.py` `social_user`: looks up `(provider, uid, id_key)`; on a miss, finds empty-key rows by `uid`.
- Evidence: `OpenIdConnectAuth.get_stored_user_id_keys("sub")` is `("sub", "id")`; 4.9.1 `EXTRA_DATA` stored `sub` as `extra_data["id"]`.
- Matching evidence: row migrated in place (`migrate_social_auth`), same user.
- Conflicting evidence: `AuthAssociationError(code="identifier_migration_conflict")`, no new row or user.
- No evidence: refused unless `allow_unverified_legacy_uid_migration`; `social_core/identifiers.py` lists no OIDC backend, so it is `False`.
- So `ALLOW_UNVERIFIED_LEGACY_UID_MIGRATION` is not needed: backfill covers both providers, runtime evidence covers stragglers.

## Acceptance criteria

1. `pyproject.toml` requires `social-auth-app-django>=7.2,<8`; `uv.lock` has core 6.2.x.
2. `GET /login/zitadel/` returns 405; POST without CSRF token returns 403.
3. POST with token and `next` starts the login and stores the sanitised `next`.
4. Wagtail and DRF login pages render one POST form per provider with `csrfmiddlewaretoken` and `next` (only when `next` is set).
5. `GET /api/auth/providers/` response is unchanged.
6. Every existing `auth_error` code still results from the same scenarios (`test_login_flow`, `test_middleware`).
7. A pre-upgrade Auth0 row (`id_key=""`, `extra_data.id == uid`) logs in as the same user; row gets `id_key="sub"`.
8. Same for a pre-upgrade Zitadel row.
9. A legacy row with conflicting `extra_data.id` is refused (`login_failed`); user and row counts unchanged.
10. A legacy row with a different uid but the same email is refused (`email_in_use`); no second user.
11. Migrating `social_django` from `0019` to latest backfills `id_key="sub"` for `zitadel` and `auth0_openidconnect` rows.
12. `uv run invoke lint`, `uv run invoke test`, `uv run invoke test --postgres` pass.
13. Manual Wagtail admin sign-in with Zitadel or Auth0 works on a port-8081 worktree stack.

## Design

- Templates: replace `<a href>` with `<form method="post" action="{% url 'social:begin' ... %}">`, `{% csrf_token %}`, hidden `next` (only when `next` is set), `<button>`.
- Wagtail `above_login` sits before Wagtail's `<form>` (Wagtail 8.1 `wagtailadmin/login.html`), so no nested forms.
- Keep classes: `button` (Wagtail), `btn btn-primary form-control` (DRF).
- `oidc_auth/exceptions.py`: rename class attribute `code` to `auth_error`; base `LoginRefused` on `AuthPolicyError`.
- Trade-off: overriding `__init__` to pass `code=` would keep the name but mix our codes into library `REASONS` metadata.
- `oidc_auth/middleware.py` `_refusal`: `LoginRefused` → `auth_error`.
- `AuthAssociationError` with `code == "identity_in_use"` → `already_signed_in`.
- Any other `AuthException` → `login_failed` (includes `identifier_migration_conflict`, `username_in_use`).
- Change: `username_in_use` was `already_signed_in` via `AuthAlreadyAssociated`; `get_username` makes it unreachable.
- `oidc_auth/pipeline.py` `create_user`: catch `IntegrityError` (the unrecognised `LOWER(email)` index); `email_owner` set → `EmailOwnedElsewhere`, else re-raise.
- Settings `recipe_cms/settings/base.py`: add `social_names` after `social_details`; add `SOCIAL_AUTH_OLD_ID_KEYS = {"zitadel": "sub"}`.

## Implementation steps

### Increment 1: POST login forms (works on 5.9.0 too)

1. `oidc_auth/templates/wagtailadmin/login.html:5`: POST form per provider.
2. `oidc_auth/templates/rest_framework/login.html:13`: POST form per provider, same look.
3. Tests `oidc_auth/tests/test_login_pages.py`, `test_local_login.py:107`: assert `action=`, `method="post"`, `csrfmiddlewaretoken`, `next` value (and its absence without `next`).
4. `oidc_auth/tests/test_login_flow.py:62` and `home/tests/test_dev_frontend_origins.py:146`: start logins with `client.post`.
5. `README.md:104,401,452`: `login_url` is a POST target needing `csrfmiddlewaretoken` (from `/api/csrf/`).

### Increment 2: refusal code rename (works on 5.9.0 too)

6. `oidc_auth/exceptions.py`: `code` → `auth_error` on all `LoginRefused` classes.
7. `oidc_auth/middleware.py:28,30`: read `auth_error`.
8. Tests `test_ownership_pipeline.py:67,135,148`, `test_pipeline.py:301`: assert `auth_error`.

### Increment 3: bump and adapt

9. `pyproject.toml:13` to `>=7.2,<8`; `uv lock --upgrade-package social-auth-app-django`.
10. `base.py:200`: insert `social_names`; base `LoginRefused` on `AuthPolicyError`.
11. `middleware.py`: new mapping and docstring; drop `AuthAlreadyAssociated` import.
12. `pipeline.py` `create_user`: catch `IntegrityError`; update docstring.
13. `test_middleware.py`: replace removed classes with `AuthAssociationError`, `AuthPolicyError`, `AuthSessionError`, `AuthCredentialError`; add `identifier_migration_conflict` → `login_failed`.
14. `test_ownership_pipeline.py:218`: expect `AuthAssociationError` with `code == "username_in_use"`.
15. `test_login_flow.py`: rows created with `id_key="sub"`; add 405 on GET, 403 via `Client(enforce_csrf_checks=True)`.
16. `test_login_flow.py`: assert `social_names` directly follows `social_details`.
17. Fix mypy fallout if the new wheels ship typing (`warn_unused_ignores`, e.g. `pipeline.py:123`).

### Increment 4: existing users (`id_key`)

18. `base.py`: `SOCIAL_AUTH_OLD_ID_KEYS = {"zitadel": "sub"}` with a one-line why-comment.
19. New `oidc_auth/tests/test_legacy_associations.py`: Zitadel harness as `test_login_flow.complete`; Auth0 harness patching `Auth0OpenIdConnectAuth.auth_complete`/`user_data`.
20. Tests: AC 7, 8 (legacy rows with `extra_data={"id": uid}`), AC 9 (conflicting `id`), AC 10 (other uid, same email).
21. Each asserts `User` and `UserSocialAuth` counts and `_auth_user_id`.
22. New `oidc_auth/tests/test_id_key_backfill.py`: `TransactionTestCase` with `MigrationExecutor`.
23. Roll back to `social_django.0019_oidc_nonce_lifetime`, insert rows via historical model, migrate to latest, assert AC 11.

### Increment 5: docs

24. `CLAUDE.md` `oidc_auth` bullet: POST-only login start, `auth_error` mapping, `SOCIAL_AUTH_OLD_ID_KEYS`.
25. `README.md`: forward-only `social_django` migrations; rollback to 5.x needs reverse migrations first.

## Verification

- `uv run invoke format`, `uv run invoke lint`, `uv run invoke test` after each increment.
- `uv run invoke test --postgres` after increments 3 and 4 (email race, backfill on Postgres).
- In the worktree: `$DEV_STACK env --port 8081`, then `uv run invoke dev --build`.
- Run `migrate`; sign in at `localhost:8081/admin/login/` with Zitadel (or Auth0); check `GET /login/zitadel/` is 405.
  Agent check reached the provider redirect only; real sign-in waived in the spec (maintainer to do before release).
- With a pre-existing row from a 5.9.0 stack if available: same user after sign-in (waived with the above; maintainer to do).
- Stop watch, then `uv run invoke down --volumes`.

## Risks

- `test_login_flow.complete` patches `auth_complete`; 6.x OIDC nonce/state binding may need harness tweaks.
- 7.2 checks the cookie-session user against the flow session; `force_login` tests may change behaviour.
- Rows with `id_key=""` and no `extra_data.id` after backfill are refused; backfill makes this unlikely.
- A branch DB migrated without `SOCIAL_AUTH_OLD_ID_KEYS` leaves Zitadel rows unkeyed; runtime evidence path covers them.
- 7.2 partial-pipeline encoding: all workers deploy together; in-progress logins restart (spec: acceptable).
- Merge order: recipes-frontend PR first, else frontend sign-in gets 405.

## Open questions

- None blocking; `ALLOW_UNVERIFIED_LEGACY_UID_MIGRATION` is not needed per the facts above.
- If increment 4 tests show legacy rows refused despite evidence: stop and ask before enabling it.
- Decided: `username_in_use` → `login_failed` (user confirmed).
