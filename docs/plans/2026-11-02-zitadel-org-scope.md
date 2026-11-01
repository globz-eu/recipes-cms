# Request the Zitadel org scope for ZITADEL_ROLE_ORG_ID at login (recipes-cms #28)

Base: `main` of recipes-cms at v0.11.0 (after recipes-cms PR #27, which made `ZITADEL_ROLE_ORG_ID`
required when `zitadel` is enabled).

## Context and goal

`ZitadelOpenIdConnect` (`src/oidc_auth/backends.py`) requests only `openid profile email
urn:zitadel:iam:org:project:roles`. Without an org scope the Zitadel login UI uses the **instance
default** login settings and branding, not the ones of the stack org `recipes-cms-<stack>` that
recipes-infrastructure manages (`src/zitadel.ts`: `allowRegister: false`, `allowExternalIdp: false`,
`forceMfa = zitadelEnforceMfa`, `ignoreUnknownUsernames: true`). That is why
recipes-infrastructure `docs/staging-bootstrap.md` step 6 requires a manual "Register allowed = off"
on the instance policy, and why recipes-infrastructure issue #6 asks to confirm that `forceMfa`
applies.

Goal: request `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>` at every Zitadel login, so Zitadel
applies the stack org's login policy and branding and only lets that org's users sign in; refuse,
with a distinct `auth_error`, a token whose user does not belong to that org. Also fix the README
statement that the Zitadel dev redirect URI is "registered for port 8080 only".

### What Zitadel does (official docs)

- `urn:zitadel:iam:org:id:{id}`: "ZITADEL will enforce that the user is a member of the selected
  organization. If the organization does not exist a failure is displayed." It also asserts the
  resource owner claims (`urn:zitadel:iam:user:resourceowner:id` etc.).
  https://zitadel.com/docs/apis/openidoauth/scopes
- "By default, the ZITADEL Login uses the instance default settings ... you must provide the
  organization scope in your authentication request" to get the org's settings and branding.
  https://zitadel.com/docs/concepts/structure/organizations
- Triggering the org in the auth request: "Trigger organization login behavior settings", "Trigger
  organization branding", "Only allow users from selected organization to login".
  https://zitadel.com/docs/guides/solution-scenarios/configurations
- `urn:zitadel:iam:org:domain:primary:{domain}`: same enforcement plus the username must carry the
  domain suffix; it broke email login names in the past (zitadel issue #6868, fixed in PR #7446). Not
  used: we have the id, not a stable domain. https://github.com/zitadel/zitadel/issues/6868
- `urn:zitadel:iam:org:project:id:{projectid}:aud` adds a project to the access-token audience and
  `urn:zitadel:iam:org:projects:roles` asserts `urn:zitadel:iam:org:project:{projectid}:roles` for
  those audience projects. Not needed: the app belongs to the only project, and we read
  `urn:zitadel:iam:org:project:roles` from the ID token.
- `urn:zitadel:iam:org:roles:id:{orgID}` is the only scope that filters the roles claim ("limit the
  granted organization IDs in the returned roles"; without it "all granted organizations are
  returned"). https://zitadel.com/docs/apis/openidoauth/scopes
- Roles claim shape: `{"<role>": {"<orgId>": "<primaryDomain>", ...}}`
  (https://zitadel.com/docs/apis/openidoauth/claims). The org-id scope does not change it, so
  `read_zitadel_roles` (keys whose grant object contains `ZITADEL_ROLE_ORG_ID`) stays correct and
  unchanged.

### Non-members of the org

- Since Zitadel v4.12.3 the org-id scope accepts only users whose **resource owner** is that org;
  users who merely hold grants in it are refused (maintainer: the scope "is to restrict the sign in
  process to users of a certain organization", cross-org tokens were "never intended to work").
  The refusal happens **inside the Zitadel login UI** (user not found / no session), not as a
  callback to the CMS. https://github.com/zitadel/zitadel/issues/11869
- With the stack org's `ignoreUnknownUsernames: true`, a non-member sees Zitadel's generic
  "invalid username or password" and never reaches `/complete/zitadel/`. Nothing for the CMS to
  surface in the normal case.
- If Zitadel returns an OAuth error to the callback (`error=access_denied`, `login_required`, ...),
  social-core raises `AuthCanceled`/`AuthFailed`, which `LoginRefusedMiddleware` already maps to
  `login_failed`. No change needed.
- A past bypass let a `login_hint` of another org override the org scope (zitadel issue #8588,
  fixed in PR #8748, Oct 2024). https://github.com/zitadel/zitadel/issues/8588 This is the reason for
  a cheap defence-in-depth check on the CMS side: refuse a token whose
  `urn:zitadel:iam:user:resourceowner:id` is present and differs from `ZITADEL_ROLE_ORG_ID`
  (new code `org_mismatch`).
- Members of the org **without grants** still sign in (the project has `projectRoleCheck: false`)
  and get no roles: `sync_roles` clears mapped groups and staff/superuser, as today. Unchanged.

## Acceptance criteria

1. `ZitadelOpenIdConnect().get_scope()` contains `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>`
   exactly once, plus `openid`, `profile`, `email` and `urn:zitadel:iam:org:project:roles`, and not
   `offline_access`.
2. `GET /login/zitadel/` redirects to the Zitadel authorization endpoint with a `scope` query value
   that contains the org-id scope.
3. With `ZITADEL_ROLE_ORG_ID` blank, `get_scope()` raises `ImproperlyConfigured` (same message
   style as `read_zitadel_roles`), never sending `urn:zitadel:iam:org:id:`.
4. A Zitadel login whose `urn:zitadel:iam:user:resourceowner:id` claim (ID token first, then
   userinfo, via `read_claim`) differs from `ZITADEL_ROLE_ORG_ID` is refused with `LoginRefused`
   code `org_mismatch`, before any user or `UserSocialAuth` is created; with a safe `next` the
   redirect carries `auth_error=org_mismatch`, otherwise the Wagtail login page shows the message.
5. A matching claim, or an absent claim, does not refuse the login (absent is logged at warning
   level); Auth0 logins are never checked.
6. `read_zitadel_roles` behaviour and tests are unchanged.
7. README: the Zitadel setup states that the org scope is requested automatically and what it
   enforces; "Refused logins" lists `org_mismatch`; the dev redirect URI sentence no longer says
   "port 8080 only" (see increment 3); CLAUDE.md lists `org_mismatch` among the `auth_error` codes.
8. `uv run invoke test --label=oidc_auth` and `uv run invoke format` pass.

## Design

### Where the scope goes: the backend (chosen) vs. settings

- **Backend (chosen):** override `get_scope()` in `ZitadelOpenIdConnect`:
  `[*super().get_scope(), f"urn:zitadel:iam:org:id:{org_id}"]`, reading
  `django.conf.settings.ZITADEL_ROLE_ORG_ID` (not `self.setting(...)`, which would look up
  `SOCIAL_AUTH_ZITADEL_ROLE_ORG_ID`). Next to the roles scope, testable with `override_settings`,
  and the same setting that `read_zitadel_roles` uses, so login scoping and role trust cannot
  diverge. `super().get_scope()` keeps `SOCIAL_AUTH_ZITADEL_SCOPE` / `IGNORE_DEFAULT_SCOPE` working;
  the org scope is appended even with `IGNORE_DEFAULT_SCOPE` (it is a security property, not a
  default). De-duplicate if someone also lists it in `SOCIAL_AUTH_ZITADEL_SCOPE`.
- **Settings (rejected):** `SOCIAL_AUTH_ZITADEL_SCOPE = [f"urn:zitadel:iam:org:id:{...}"]` in
  `base.py` would need a conditional for blank ids, splits Zitadel logic across files and is
  silently dropped by any later override of that setting.
- Blank id: raise `ImproperlyConfigured`, as `read_zitadel_roles` does. Settings already refuse a
  blank id when `zitadel` is enabled, so this only fires in misconfigured tests.

### Not added

- `urn:zitadel:iam:org:roles:id:{orgID}`: would duplicate the filter in `read_zitadel_roles`; with
  `hasProjectCheck` and users living in the stack org there are no foreign grants anyway. See open
  question 2.
- `urn:zitadel:iam:user:resourceowner`: the org-id scope already asserts the resource owner claims.

### Org check (defence in depth)

- `src/oidc_auth/exceptions.py`: `class OrgMismatch(LoginRefused)` with `code = "org_mismatch"`,
  `message = "This account does not belong to this site's sign-in organisation."`
- `src/oidc_auth/pipeline.py`: `enforce_zitadel_org(backend, response, *args, **kwargs)`; no-op
  unless `backend.name == "zitadel"`; reads `urn:zitadel:iam:user:resourceowner:id` with
  `providers.read_claim`; raises `OrgMismatch(backend)` when present and `!= ZITADEL_ROLE_ORG_ID`;
  logs a warning and continues when absent. Constant
  `ZITADEL_RESOURCE_OWNER_CLAIM = "urn:zitadel:iam:user:resourceowner:id"` in `providers.py` next to
  `ZITADEL_ROLES_CLAIM`.
- `src/recipe_cms/settings/base.py` `SOCIAL_AUTH_PIPELINE`: insert
  `"oidc_auth.pipeline.enforce_zitadel_org"` right after `social_core.pipeline.social_auth.auth_allowed`
  (before `social_user`), so nothing is looked up, created or associated for a foreign user.
- `LoginRefusedMiddleware` needs no change (it handles every `LoginRefused`). recipes-frontend maps
  unknown codes to `login_failed` (`src/auth/urls.ts`), so the new code degrades gracefully there.

### Files

| File | Change |
|---|---|
| `src/oidc_auth/backends.py` | `get_scope()` override, `ZITADEL_ORG_SCOPE_PREFIX = "urn:zitadel:iam:org:id:"` |
| `src/oidc_auth/providers.py` | `ZITADEL_RESOURCE_OWNER_CLAIM` constant |
| `src/oidc_auth/exceptions.py` | `OrgMismatch` |
| `src/oidc_auth/pipeline.py` | `enforce_zitadel_org` |
| `src/recipe_cms/settings/base.py` | pipeline entry |
| `src/oidc_auth/tests/test_backends.py`, `test_pipeline.py`, `test_login_flow.py` | tests |
| `README.md`, `CLAUDE.md` | docs |

## Implementation steps

1. **Org scope in the backend** (`backends.py`, `tests/test_backends.py`). Add the `get_scope()`
   override. Tests (`SimpleTestCase`, `@override_settings(ZITADEL_ROLE_ORG_ID="123456")` on the
   class): scope contains `urn:zitadel:iam:org:id:123456` once; still has `openid` and the roles
   scope; no `offline_access`; with `SOCIAL_AUTH_ZITADEL_SCOPE` listing the org scope it appears once;
   with `SOCIAL_AUTH_ZITADEL_IGNORE_DEFAULT_SCOPE=True` it is still present; blank id raises
   `ImproperlyConfigured`. In `tests/test_login_flow.py` (its class already overrides the Zitadel
   settings; add `ZITADEL_ROLE_ORG_ID` if not there on `main` of recipes-cms): `GET /login/zitadel/`
   with `ZitadelOpenIdConnect.oidc_config` patched to return an `authorization_endpoint`; assert
   the redirect's `scope` parameter, split on spaces, contains the org scope. Commit:
   `feat(oidc_auth): request the Zitadel org scope for ZITADEL_ROLE_ORG_ID`.
2. **Refuse foreign resource owners** (`exceptions.py`, `providers.py`, `pipeline.py`, `base.py`,
   `tests/test_pipeline.py`, `tests/test_login_flow.py`). Unit tests: match passes, mismatch raises
   `OrgMismatch`, ID-token value wins over userinfo, absent claim passes and logs (`assertLogs`),
   Auth0 backend is ignored. Flow test: complete a Zitadel login with a mismatching claim and a
   safe `next`; expect a redirect with `auth_error=org_mismatch` and no new `User` /
   `UserSocialAuth`. Commit: `feat(oidc_auth): refuse Zitadel users of another org`.
3. **Docs** (`README.md`, `CLAUDE.md`).
   - Zitadel setup step 3: "The roles scope is requested automatically" becomes "The roles scope and
     `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>` are requested automatically"; step 6 explains
     that this makes Zitadel use that org's login settings (registration, MFA) and branding and
     only admit its users.
   - Step 4: replace "registered for port 8080 only" with: the recipes-infrastructure dev stack
     registers `http://localhost:8080` plus `localExtraPorts` (8081-8089) and the dev server
     ports (5173, `localExtraDevServerPorts` 5174-5182) for Zitadel the same way as for Auth0, once
     `enableZitadel` is uncommented in its `Pulumi.dev.yaml`. Verified: `localAuthUrls` in
     recipes-infrastructure `src/urls.ts` builds `zitadelCallbackUrls` and `zitadelLogoutUrls` from
     the same origin lists as Auth0, and `src/config.ts` passes that one object as both `auth0Urls`
     and `zitadelUrls`; `src/zitadel.ts` uses them for `redirectUris` / `postLogoutRedirectUris`.
   - "Parallel stacks (git worktrees)": "Social login (Auth0) works on nginx ports 8080-8089" becomes
     "Social login (Auth0, and Zitadel when the dev stack enables it) works on ...".
   - "Refused logins": add `org_mismatch`. CLAUDE.md `oidc_auth` bullet: add `org_mismatch` to the
     code list and mention the org scope.
   Commit: `docs: document the Zitadel org scope and dev ports`.
4. **Manual verification on the dev stack** (no commit; report in the PR). With `enableZitadel` on
   the recipes-infrastructure `dev` stack: (a) the Zitadel login shows the stack org's branding and
   no "Register" link; (b) a user of the default org cannot sign in; (c) with `zitadelEnforceMfa`
   the stack-org user is forced to set up MFA; (d) whether the ID token / userinfo contains
   `urn:zitadel:iam:user:resourceowner:id` (decides open question 1); (e) a user in the org
   without grants lands on the CMS no-access page. Stop the stack afterwards
   (`uv run invoke down`).

## Test plan

- Automated (Django test runner, `src/oidc_auth/tests/`): increments 1 and 2 above;
  `uv run invoke test --label=oidc_auth`, then the full suite.
- Manual: increment 4, on port 8080 and on one worktree port (e.g. 8081) to also confirm the
  README statement of increment 3.

## Risks

- A wrong `ZITADEL_ROLE_ORG_ID` now breaks Zitadel login visibly ("organization does not exist")
  instead of just yielding empty roles. Acceptable and arguably better; mention in the release
  notes.
- Users of another org who only hold grants in the stack org can no longer sign in (Zitadel >=
  v4.12.3). The setup creates users in the stack org, so nobody is affected today.
- The resource owner claim may only be asserted in userinfo, or not at all, in the Zitadel Cloud
  version in use; the check then never fires (fail-open by design until verified).
- Zitadel login v2 behaviour around org scope and email login names has had bugs (zitadel issues
  #6868, #13019); covered by manual step 4.
- Not deployed anywhere yet with Zitadel (staging still `local,auth0`), so rollout risk is low.

## Follow-ups (other repos, not in this change)

- recipes-infrastructure: once a recipes-cms release ships this, reword README "Self-registration
  needs a manual step" / "Cross-repo follow-up" and `docs/staging-bootstrap.md` step 6 (keep the
  instance-policy step as a backstop: the login UI can still be opened without the scope), and note
  the result of the `forceMfa` check in issue #6.
- recipes-frontend: add an `org_mismatch` message to `AUTH_ERROR_MESSAGES` (optional, falls back to
  `login_failed`).

## Open questions

1. Absent `urn:zitadel:iam:user:resourceowner:id`: allow with a warning (planned) or refuse
   (fail-closed)? Decide after manual check 4(d); if the claim is reliably present, fail-closed is
   stricter at no cost.
2. Also request `urn:zitadel:iam:org:roles:id:<ZITADEL_ROLE_ORG_ID>` so Zitadel itself filters the
   roles claim? Harmless, but duplicates `read_zitadel_roles`; planned: no.
3. Is a separate `org_mismatch` code wanted, or should the check reuse `login_failed` to avoid a
   frontend change? Planned: new code (clearer for admins, degrades to `login_failed` in the
   frontend).
4. Release: minor bump (v0.12.0) via `uv run invoke bump --part minor`, since login behaviour
   changes?

## Decisions (approved 2026-11-02)

1. Missing `urn:zitadel:iam:user:resourceowner:id` claim: the login proceeds and a warning is logged (the org scope is the primary control).
2. Do not request `urn:zitadel:iam:org:roles:id:<id>`; `read_zitadel_roles` already filters by org.
3. New `auth_error` code `org_mismatch` (subclass of `LoginRefused`).
4. Release as a minor bump (v0.12.0) after merge.
5. Increment 4 (manual check against a real Zitadel) is deferred to recipes-infrastructure #6: the ESC environment `recipes-infrastructure/zitadel-management` does not exist yet, so Zitadel cannot be enabled on the dev stack. This branch ships increments 1-3 with unit/integration tests only.
