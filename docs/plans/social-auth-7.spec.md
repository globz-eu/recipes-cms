# Spec: upgrade social-auth-app-django to 7.2

Source: recipes-cms issue #39. Goal: stay current, no visible change to sign-in.
Companion spec (frontend POST form, merged first): recipes-frontend `docs/plans/login-post-form.spec.md`.

### Intent

- Lift the `social-auth-app-django>=5.7,<6` cap set during the Wagtail 8.1 upgrade.
- Target `social-auth-app-django>=7.2,<8` with social-auth-core 6.x (user's choice).
- Users keep the same login buttons, redirects and `auth_error` codes.

### Non-goals

- social-auth-app-django 8.0 / social-auth-core 7 (released 2026-11-09, too fresh).
- Any login UX redesign, new providers or new `auth_error` codes.
- The recipes-frontend change (companion spec, separate PR).

### Anti-goals

- Existing Auth0/Zitadel users on staging losing their accounts or getting `email_in_use`.

### Changes

- Bump the dependency, update `uv.lock`; apply social_django migrations (adds `id_key`).
- Login starts are POST-only with CSRF (`social_django.views.auth` uses `@require_POST`).
- Wagtail admin login (`oidc_auth/templates/wagtailadmin/login.html`): POST form per provider with `{% csrf_token %}` and `next`.
- DRF login (`oidc_auth/templates/rest_framework/login.html`): same; keep the buttons' look.
- Convert every other login-start caller (`grep social:begin`, `login_url`).
- `GET /api/auth/providers/`: unchanged shape; `login_url` is now a POST target.
- Map new exception classes/`.code` in `LoginRefusedMiddleware` and `pipeline.create_user`; same `auth_error` codes.
- Pipeline: add `social_core.pipeline.social_auth.social_names` after `social_details`.
- Custom pipeline steps stop relying on the automatic `request` argument (use `strategy.request`).
- Read social-core 6.x and social-app-django 6–7.2 changelogs for OIDC/Auth0, custom backends and pipeline steps.

### Existing users (`id_key`)

- Same-`sub` rows re-key on login; tests with pre-upgrade Auth0 and Zitadel rows assert the same user logs in.
- A mismatched legacy uid refuses the login, never creates a second account.
- Do not enable `ALLOW_UNVERIFIED_LEGACY_UID_MIGRATION`; if tests show it is needed, stop and ask.
- Forward-only migrations; rolling back to 5.x needs reverse `social_django` migrations first.

### Decided

- GET on `/login/<backend>/` returns the library's 405; no redirect view.
- In-progress logins during deploy must restart; acceptable.

### Done when

- `uv run invoke lint`, `uv run invoke test`, `uv run invoke test --postgres` pass.
- Manual sign-in via Wagtail admin with a social provider works on the dev stack.
- PR says `Closes #39`; it merges after the recipes-frontend PR.

### Left to the builder

- Exact exception-to-code mapping, form markup/CSS, how tests simulate pre-upgrade associations.
