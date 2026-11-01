# Plan: require ZITADEL_ROLE_ORG_ID when zitadel is enabled (recipes-cms issue #25)

Branch: `fix/require-zitadel-role-org-id` from up-to-date `main` of recipes-cms. Do not branch from
recipes-cms branch `feature/dev-frontend-origins`: its `compose.yml` predates recipes-cms PR #21.

## 1. Context and goal

`read_zitadel_roles` (`src/oidc_auth/providers.py`) filters roles by organisation only when
`ZITADEL_ROLE_ORG_ID` is set. Its default (`base.py`: `os.getenv("ZITADEL_ROLE_ORG_ID", "")`) is
empty, which makes it count roles granted in **any** organisation, `admin` included (superuser/staff).
If the project is granted to another org, that org's admins can make their users superusers.

Goal: when `zitadel` is in `AUTH_PROVIDERS`, the variable is required at settings import, exactly
like the other provider variables. The "any organisation" fallback goes away. The user decided
there is **no opt-out value** for trusting all organisations.

Findings from the code that the plan relies on:

- `compose.yml` on recipes-cms `main` already forwards `ZITADEL_ROLE_ORG_ID:` to `wagtail`
  (recipes-cms PR #21, merged). It is missing from the working tree of branch
  `feature/dev-frontend-origins` only because that branch is older. **No compose change.**
- recipes-infrastructure needs **no change**. `src/authEnv.ts` sets `ZITADEL_ROLE_ORG_ID = zitadel.orgId`
  in `plainEnv` whenever Zitadel is enabled, and `src/app.ts` passes `plainEnv` to the container and to
  every job (migrate, collectstatic, ensure_admin). The `dev` stack exposes `localZitadel.orgId`, and
  the recipes-infrastructure README already maps it to `ZITADEL_ROLE_ORG_ID` and says "The CMS only
  trusts roles granted in this org". Staging doesn't enable Zitadel yet (recipes-infrastructure
  issue #6). Once it does, the variable is already set.
- Dockerfile line 38 runs `AUTH_PROVIDERS=local uv run manage.py collectstatic`, so the zitadel check
  doesn't run at build time. **No change.**
- `check_provider_settings` treats `None` and `""` as missing but accepts `"   "`.
- Tests switch zitadel on with `override_settings`, which doesn't re-run the import-time check. But
  `SyncZitadelRolesTestCase` and `LoginFlowTestCase` run `read_zitadel_roles` with the base default
  `""` and rely on the fallback. The full list is in section 4.
- recipes-roadmap `architectures/recipes.md` says nothing about Zitadel organisations or the CMS
  variables. **No change.**

## 2. Acceptance criteria

1. With `AUTH_PROVIDERS` containing `zitadel` and `ZITADEL_ROLE_ORG_ID` unset, empty or
   whitespace-only, importing the settings raises `ImproperlyConfigured`. The message names
   `ZITADEL_ROLE_ORG_ID` (alongside any other missing variables).
2. Without `zitadel` in `AUTH_PROVIDERS`, an unset `ZITADEL_ROLE_ORG_ID` is fine (the default
   `local,auth0` and the Dockerfile's `AUTH_PROVIDERS=local` collectstatic keep working).
3. `read_zitadel_roles` returns only roles whose grants object contains the configured org id.
   Roles granted only in other orgs, and malformed grants (`None`, string, list, `{}`), give no role.
4. If `read_zitadel_roles` runs with an empty org id anyway (for example a runtime
   `override_settings`), it raises `ImproperlyConfigured`. It never falls back to accepting all orgs
   (same pattern as `read_auth0_roles` with an empty `AUTH0_ROLES_CLAIM`).
5. A value with surrounding whitespace (`" 123 "`) matches the org id `123` in the claim.
6. `.env.example`, the README (Zitadel `.env` block, Zitadel setup step 6, production env table) and
   the `oidc_auth` bullet in CLAUDE.md describe the variable as required for `zitadel`, with no
   "optional" or "trust every org" wording left.
7. `uv run invoke test` passes. `uv run invoke format` leaves no diff.

## 3. Design

### Affected files

| File | Change |
|---|---|
| `src/oidc_auth/config.py` | Add `"ZITADEL_ROLE_ORG_ID"` to `REQUIRED_SETTINGS[ZITADEL]`. In `check_provider_settings`, also count a whitespace-only string as missing (see trade-offs). |
| `src/recipe_cms/settings/base.py` | `ZITADEL_ROLE_ORG_ID = os.getenv("ZITADEL_ROLE_ORG_ID", "").strip()`. Rewrite the comment: required with zitadel, and only roles granted in this org count. |
| `src/oidc_auth/providers.py` | `read_zitadel_roles`: read `settings.ZITADEL_ROLE_ORG_ID` first. If it's empty, raise `ImproperlyConfigured("ZITADEL_ROLE_ORG_ID must be set to sync Zitadel roles to Wagtail groups.")`. Then keep a role only if `isinstance(grants, dict) and org_id in grants`. Update the docstring. |
| `src/oidc_auth/tests/test_config.py` | Add `ZITADEL_ROLE_ORG_ID` to `ZITADEL_VALUES` and add tests (section 4). |
| `src/oidc_auth/tests/test_pipeline.py` | Update `SyncZitadelRolesTestCase` (section 4). |
| `src/oidc_auth/tests/test_login_flow.py` | Add `ZITADEL_ROLE_ORG_ID="org-1"` to the class `override_settings`. |
| `src/oidc_auth/tests/test_views.py` | Add `ZITADEL_ROLE_ORG_ID="org-1"` to the `ProviderLogoutTestCase` overrides, for consistency (logout doesn't read it). |
| `.env.example` | Under `# zitadel`, replace "Optional: only trust roles..." with a required line that points at `localZitadel.orgId`. |
| `README.md` | Only the Zitadel/env-var parts: the `.env` block (lines ~178-183), Zitadel setup step 6 (~551-555), the production env table row (~450), plus a short rollout note. Leave the "social login only works on 8080" lines (~237, ~545) alone: a parallel branch edits them. |
| `CLAUDE.md` | One clause in the `oidc_auth` bullet (line 39), e.g. after `config.py`: "zitadel also needs `ZITADEL_ROLE_ORG_ID`, and only roles granted in that org count". Don't touch the "Social login only works on 8080" sentence in Commands. |

Not changed: `compose.yml`, `Dockerfile`, `settings/dev.py`, `settings/production.py`,
recipes-infrastructure, recipes-roadmap.

### Trade-offs considered

- **Whitespace-only values.** Option A: `.strip()` in `base.py` only. A blank value then becomes
  `""` and fails the existing truthiness check, and a padded id still matches the claim. Option B:
  also make `check_provider_settings` treat whitespace-only strings as missing for every required
  variable. Option B can be unit-tested in `test_config.py`, which is pure (A by itself is only
  covered through settings import), and a whitespace-only secret or domain is just as broken.
  **Recommended: both.** The strip makes `" 123 "` work, and the generic check guards every
  variable. The generic check turns configs that are broken today into a loud error at start,
  which is the point of `check_provider_settings` (see open question 1).
- **Runtime guard in `read_zitadel_roles`.** With the import check in place it's redundant in
  production. Keep it anyway so that no code path can silently trust every org. It mirrors
  `read_auth0_roles`. It sits before the claim is read, so it fails even for a user with no roles,
  and that's why `LoginFlowTestCase` needs the setting.
- **No opt-out value** (for example `*`), as decided by the user.

## 4. Test plan

Django test runner, `src/oidc_auth/tests/`.

`test_config.py` (`CheckProviderSettingsTests`):
- `ZITADEL_VALUES` gains `"ZITADEL_ROLE_ORG_ID": "123456789"`. The existing all-present,
  disabled-provider and multiple-missing tests then cover it (multiple-missing iterates
  `ZITADEL_VALUES`).
- New `test_zitadel_role_org_id_is_required`: `ZITADEL_VALUES` without the key raises, and the
  message contains `ZITADEL_ROLE_ORG_ID`.
- New `test_whitespace_only_counts_as_missing`: subTests over `" "` and `"\t\n"` for
  `ZITADEL_ROLE_ORG_ID` (and one Auth0 variable, to pin the generic behaviour).
- New `test_auth0_only_needs_no_zitadel_org_id`: `check_provider_settings(["local", "auth0"],
  AUTH0_VALUES)` passes (AC 2).

`test_pipeline.py` (`SyncZitadelRolesTestCase`):
- Add `ZITADEL_ROLE_ORG_ID="org-1"` to the class-level `override_settings`.
- **Changed fixtures:** the grants of the roles each test expects to count go from `{}` to
  `{"org-1": "one.example"}`. This affects `test_falls_back_to_response`,
  `test_id_token_is_preferred_over_response` (both claims, so the test still proves the id-token
  preference) and `test_admin_role_sets_superuser_and_staff`. In `test_object_claim_keys_are_roles`
  change `"123"` to `"org-1"`. `"ghost": {}` can stay because it's unmapped either way. Without the
  fixture change these tests would fail, because empty grants no longer count.
- The two `@override_settings(ZITADEL_ROLE_ORG_ID="org-1")` method decorators become redundant.
  Drop them.
- **Removed and replaced:** `test_empty_org_id_accepts_roles_from_any_org` tests exactly the
  behaviour that issue #25 removes. Replace it with `test_empty_org_id_fails_loudly`:
  `@override_settings(ZITADEL_ROLE_ORG_ID="")`, a sync with `{"editor": {"org-2": ...}}` raises
  `ImproperlyConfigured`, and the user has no groups (AC 4).
- New `test_role_without_any_org_grant_is_ignored`: `{"admin": {}}` gives no superuser (AC 3).

`test_login_flow.py`: add the setting to the class overrides. Otherwise
`test_verified_new_email_creates_user_and_logs_in` reaches `sync_roles` and hits the new guard.

Settings-import check (AC 1, 5), manual, no automated test (settings are imported once per process):
```bash
docker compose exec -e AUTH_PROVIDERS=local,zitadel -e SOCIAL_AUTH_ZITADEL_DOMAIN=x.example \
  -e SOCIAL_AUTH_ZITADEL_KEY=k -e SOCIAL_AUTH_ZITADEL_SECRET=s -e ZITADEL_ROLE_ORG_ID="  " \
  wagtail uv run manage.py check            # expect ImproperlyConfigured naming ZITADEL_ROLE_ORG_ID
# same with ZITADEL_ROLE_ORG_ID=" 123 " -> check passes; manage.py shell -c
#   "from django.conf import settings; print(repr(settings.ZITADEL_ROLE_ORG_ID))" prints '123'
```
Also run `docker compose build wagtail` to confirm that the build-time collectstatic still succeeds
(AC 2).

Optional end-to-end check, only with a Zitadel dev app (recipes-infrastructure `dev` stack with
`enableZitadel`): set `ZITADEL_ROLE_ORG_ID` from `localZitadel.orgId`, then sign in at
`localhost:8080/login/zitadel/` with a granted user and confirm the groups. Whoever starts the stack
stops it (`uv run invoke down`).

## 5. Implementation increments

1. **Require the variable at import** (`config.py`, `base.py`, `test_config.py`). Add it to
   `REQUIRED_SETTINGS`, add the whitespace-only check, `.strip()` in `base.py`, and the
   `test_config.py` tests.
   Commit: `fix(oidc_auth): require ZITADEL_ROLE_ORG_ID when zitadel is enabled`.
2. **Drop the any-org fallback** (`providers.py`, `test_pipeline.py`, `test_login_flow.py`,
   `test_views.py`). Add the guard plus the strict grant check, and the test changes from
   section 4. Commit: `fix(oidc_auth): only trust Zitadel roles granted in ZITADEL_ROLE_ORG_ID`.
3. **Docs** (`.env.example`, `README.md` Zitadel/env-var sections only, `CLAUDE.md` `oidc_auth`
   bullet). README rollout note: "Deployments with `zitadel` enabled must set `ZITADEL_ROLE_ORG_ID`
   before upgrading, or the app refuses to start; recipes-infrastructure already sets it."
   Commit: `docs: ZITADEL_ROLE_ORG_ID is required with zitadel`.
4. Run `uv run invoke format` and `uv run invoke test` (pipe through `cat`), then do the manual
   import check.

Increments 1 and 2 can be one commit if preferred. Each keeps the test suite green on its own.

## 6. Risks

- **Breaking for deployments with zitadel but no org id.** They now fail at start (the container
  and every job import the settings). Known environments are covered: staging doesn't enable
  Zitadel, and recipes-infrastructure sets the variable whenever it does. Local `.env` files with
  `zitadel` need the `localZitadel.orgId` value. The worktree `.env` files from `worktree-env` copy
  it from the main worktree's `.env`.
- **Generic whitespace check** could reject an existing `.env` that has a whitespace-only value for
  an enabled provider's variable. Such a config is broken today anyway.
- **README conflicts** with the parallel branch: kept small by not touching lines ~237 and ~545.
  Step 6 (~551) is close to step 4 (~544-548). Rebase whichever lands second.

## 7. Open questions

1. Should the whitespace-only check apply to **all** required provider variables (recommended) or
   only to `ZITADEL_ROLE_ORG_ID` (strip in `base.py` only)?
2. Keep the runtime `ImproperlyConfigured` guard in `read_zitadel_roles` (recommended, mirrors
   Auth0), or rely on the import check only and let an empty org id simply match nothing?
3. Release: this is a breaking config change for zitadel deployments. Is `uv run invoke bump --part
   minor` right for the next release, and should the release notes call it out?
4. Should the recipes-infrastructure README's "Cross-repo follow-up" (send the scope
   `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>`) get its own recipes-cms issue now that the
   variable is always present? Out of scope here.

## 8. Decisions (approved 2026-11-01)

1. Whitespace-only values count as missing for **all** required provider variables in `check_provider_settings`.
2. Keep the runtime `ImproperlyConfigured` guard in `read_zitadel_roles`.
3. Release: next release is a minor bump with a release-note callout (the bump itself is not part of this branch; the PR description calls out the breaking config change).
4. The `urn:zitadel:iam:org:id:<ZITADEL_ROLE_ORG_ID>` scope gets its own recipes-cms issue, out of scope here.
