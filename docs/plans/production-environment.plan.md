# Plan: production environment

Spec: [production-environment.spec.md](production-environment.spec.md) (source of truth).
Ticket: [recipes-infrastructure issue #21](https://github.com/globz-eu/recipes-infrastructure/issues/21).

## Context and goal

- Add stacks `production` (identity) and `production-runtime` to the existing Pulumi program.
- Nothing committed may identify production; the repo goes public next ([recipes-infrastructure issue #26](https://github.com/globz-eu/recipes-infrastructure/issues/26)).
- Production is Zitadel-only, has protected data and no developer surfaces.
- It deploys only through a quiet, manual "Production" workflow.
- Delivery: recipes-cms pull request and release first, then the recipes-infrastructure pull request.

## Decisions (builder's calls the spec left open)

- recipes-cms env vars: `ENABLE_BROWSABLE_API`, `ENABLE_DJANGO_ADMIN` ("true"/"false"; unset or empty means on).
- Infra config keys: `enableBrowsableApi`, `enableDjangoAdmin` (runtime, default off).
- Infra config key `protectData` (runtime, default on): sets `protect` and drops `forceDestroy`.
- `enableLocalLogin` default flips to off in `loadIdentityConfig`; local stacks keep their hardcoded `true`.
- Staging sets every switch explicitly in its committed files; production sets none.
- Runtime ESC keys: `identityStack`, `projectId`, `containerPort`, `scaleway:region`, `enableBackups`.
- ESC environments: `production-config`, `production-runtime-config`, `scaleway-production-credentials`, `integration-tests-production`.
- `integration-tests-production` imports `integration-tests`, overrides `BACKUP_READ_*` with production's reader key.
- The shared test user `recipes-integration-tests` becomes `ORG_OWNER_VIEWER` of the production org.
- The workflow calls the CI-only script `scripts/deploy-production.sh`; the script refuses to run outside GitHub Actions.
- Production pins `recipes-cms:v0.20.0`, the expected `invoke bump --part minor` result after v0.19.0.
- A unit test requires the production image to be v0.20.0 or newer.
- No setup doc is renamed; `docs/staging-bootstrap.md` gains a short "Production" section.

## Acceptance criteria

Goal 1, stacks:
1. Production program run gives fixed hosts `<appSubdomain>.<baseDomain>` and `static.<app host>`: `tests/unit/program-production.test.ts`.
2. `production.yml` has no destroy step and never calls `destroy-staging.sh`: `tests/unit/production-workflow.test.ts`.

Goal 2, nothing identifying:
3. `Pulumi.production.yaml` parses to exactly `{environment}`: `tests/unit/stack-files.test.ts`.
4. `Pulumi.production-runtime.yaml` holds only `environment`, `containerImage`, `frontendVersion`: `stack-files.test.ts`.
5. Neither file holds UUIDs, ids of 6+ digits or the forbidden config key names: `stack-files.test.ts`.
6. The production image tag is v0.20.0 or newer: `stack-files.test.ts`.

Goal 3, Zitadel only:
7. Production container gets `AUTH_PROVIDERS=zitadel` and no ensure-admin job: `program-production.test.ts`.
8. Production declares no Auth0 resource: `program-production.test.ts`.
9. Live: the Zitadel org is named `recipes-cms-production`: the existing `tests/integration/zitadel.test.ts`.

Goal 4, protected data:
10. Without `protectData`: `recipes-db` and `recipes-assets` have `protect`, and the bucket has `forceDestroy: false`: `tests/unit/program-runtime-protection.test.ts`.
11. With staging's `protectData: "false"`: no `protect`, `forceDestroy: true`, same logical names: `program-runtime-protection.test.ts`.

Goals 5 and 6, recipes-cms switches:
12. `ENABLE_BROWSABLE_API=false`: `/api/` answers JSON to `Accept: text/html`: `src/home/tests/test_optional_urls.py`.
13. `ENABLE_BROWSABLE_API=false`: `/api-auth/login/` is 404, `rest_framework:login` does not reverse: `test_optional_urls.py`.
14. `ENABLE_BROWSABLE_API=false`: `LOGIN_URL` is `/admin/login/`: `src/home/tests/test_settings_env.py`.
15. `ENABLE_DJANGO_ADMIN=false`: `/django-admin/` is 404, `/admin/login/` still 200: `test_optional_urls.py`.
16. Both off: `/admin/` and `/api/` pages render without `NoReverseMatch`: `test_optional_urls.py`.
17. Unset or empty: both on, as today: `test_settings_env.py` plus the unchanged suite.
18. Any other value fails at settings import with `ImproperlyConfigured`: `test_settings_env.py`.
19. Live: surfaces match `deployment.cmsSwitches` on each stack: `tests/integration/cms-switches.test.ts`.

Goal 6a, fail-safe defaults:
20. An identity stack without `enableLocalLogin` has no `local` provider: `tests/unit/config-auth.test.ts`.
21. A runtime without the switch keys sets both `ENABLE_*` to `"false"`: `tests/unit/program-runtime-cms-switches.test.ts`.
22. Staging files set `enableLocalLogin`, both switches `"true"` and `protectData: "false"`: `stack-files.test.ts`.
23. `dev/compose.yml` sets both `ENABLE_*` to `"true"`: `tests/unit/dev-stack-compose-file.test.ts`.

Goal 7, seed:
24. `import-recipes.sh --session` reads the cookie from stdin and never puts it in arguments or output: `tests/unit/import-recipes-session.test.ts`.
25. With `--session`, the script makes no admin login and reads no admin credentials: `import-recipes-session.test.ts`.
26. A refused session (no `/admin/` 200) exits non-zero before uploading: `import-recipes-session.test.ts`.

Goal 8, backups:
27. `backedUpStacks` is `[production]`, and the check has `schedule` cron `30 6 * * *`: `tests/unit/backup-check-workflow.test.ts`.
28. `Pulumi.production-runtime.yaml` attaches `backup-writer-production`: `stack-files.test.ts`.

Goal 9, Production workflow:
29. Dispatch only, `main` only, environment `production`, concurrency `production`: `production-workflow.test.ts`.
30. The mask step runs before any step that reads the stacks or deploys: `production-workflow.test.ts`.
31. The token reaches only the mask, deploy, cancel and checks steps: `production-workflow.test.ts`.
32. No e2e, Playwright, `upload-artifact` or destroy; actions are pinned to a SHA: `production-workflow.test.ts`.
33. The deploy script refuses without `GITHUB_ACTIONS=true`: `tests/unit/deploy-production.test.ts`.
34. It runs identity then runtime, and stops if identity fails: `deploy-production.test.ts`.
35. It passes `--suppress-outputs` and `--message "<run url> <sha>"`: `deploy-production.test.ts`.
36. It prints the result and Pulumi update link, never the `pulumi up` output: `deploy-production.test.ts`.
37. The mask script masks each listed value and fails if a key is missing: `tests/unit/mask-production-values.test.ts`.
38. The checks script prints counts and failing test names only, no failure messages: `tests/unit/production-checks.test.ts`.

Goal 10, docs:
39. No doc tells anyone to run `pulumi up`/`destroy` on a production stack: `tests/unit/production-docs.test.ts`.
40. README, CLAUDE.md, `docs/environments.md`, `docs/permissions.md`, bootstrap updated: review.

## Design

### recipes-cms

- `settings/base.py`: new pure `env_flag(name, default)`, next to `env_list`.
- `env_flag` accepts `true`/`false` (any case); unset or blank gives the default; anything else raises `ImproperlyConfigured`.
- `ENABLE_BROWSABLE_API`, `ENABLE_DJANGO_ADMIN` settings, both defaulting to `True`.
- `REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"]`: `JSONRenderer`, plus `BrowsableAPIRenderer` only when enabled.
- `LOGIN_URL`: `/api-auth/login/` when enabled, else `f"/{WAGTAIL_ADMIN_BASE_PATH}/login/"`.
- `recipe_cms/urls.py`: `django-admin/` mounted only with `settings.ENABLE_DJANGO_ADMIN`.
- `recipe_cms/urls.py`: both `api-auth/` patterns (incl. `rest_framework_logout`) only with `settings.ENABLE_BROWSABLE_API`.
- `INSTALLED_APPS` unchanged: no migration or permission changes.
- Tests reload `recipe_cms.urls` under `override_settings`, `clear_url_caches()`, and reload again in `tearDown`.
- This follows the reload pattern in `home/tests/test_cookie_names.py`.

### recipes-infrastructure: config and resources

- `src/config/readCmsSwitches.ts` (new): `enableBrowsableApi`, `enableDjangoAdmin`, both `?? false`.
- `readPlatformSettings.ts`: `protectData: config.getBoolean("protectData") ?? true`.
- `StackConfig` (`stackConfig.ts`): `enableBrowsableApi`, `enableDjangoAdmin`, `protectData`.
- `loadRuntimeConfig.ts` spreads `readCmsSwitches(config)`.
- `loadIdentityConfig.ts:49`: `enableLocalLogin ?? false`.
- `src/app/productionEnv.ts`: always sets `ENABLE_BROWSABLE_API` and `ENABLE_DJANGO_ADMIN` explicitly, as with `AUTH_PROVIDERS`.
- `src/dataProtection.ts` (new): `dataResourceOptions(protectData)` returns `{ protect: true }` or `{}`.
- `src/database.ts` (`recipes-db`) and `src/storage.ts` (`recipes-assets`) pass those options.
- `recipes-assets` gets `forceDestroy: !cfg.protectData`.
- `protect: false` and `{}` are the same to the engine, and logical names stay the same, so staging's URNs and state don't change.
- `deploymentOutputs.ts`: `deployment.cmsSwitches: { browsableApi, djangoAdmin }` for the integration tests.

### Stack files and ESC

- `Pulumi.production.yaml`: `environment: [zitadel-management, production-config]`.
- `Pulumi.production-runtime.yaml` environments: `scaleway-production-credentials`, `zitadel-management`, `dnsimple`, `production-runtime-config`, `backup-writer-production`.
- `Pulumi.production-runtime.yaml` config: only `containerImage` (`recipes-cms:v0.20.0`) and `frontendVersion` (`v0.8.0`).
- `production-config` `pulumiConfig`: `baseDomain`, `appSubdomain`, `enableCdn`, `enableZitadel`, `zitadelOrgId`, `zitadelEnforceMfa`, `zitadelTestUserId`.
- `production-runtime-config` `pulumiConfig`: `identityStack`, `projectId`, `containerPort`, `scaleway:region`, `enableBackups`.
- The stack name `production` gives resource names `/recipes/production` and `cms-production-generated` (no admin in it).

### Workflow and CI scripts

- `.github/workflows/production.yml`: `workflow_dispatch`, `if: github.ref == 'refs/heads/main'`, `environment: production`.
- `production.yml` also has `concurrency: production` (no cancel) and `permissions: contents: read`.
- Steps: checkout, Pulumi CLI, mask, Node, `npm ci`, scw, deploy, cancel-on-failure, checks.
- `scripts/ci/mask-production-values.sh`: `pulumi env open` both config environments into variables.
- It prints `::add-mask::` for `baseDomain`, app host, static host, `projectId`, `zitadelOrgId`, `zitadelTestUserId`.
- It names keys explicitly, so it doesn't over-mask values like `true`, and fails on a missing key.
- `scripts/deploy-production.sh`: `pulumi up --yes --suppress-outputs --message ...` per stack.
- Each `pulumi up` writes to `$RUNNER_TEMP/<stack>.log`, never uploaded.
- The script prints `<stack>: succeeded|failed (exit N)` and the `https://app.pulumi.com/.../updates/N` link grepped from the log.
- Cancel step: `pulumi cancel --yes` per production stack, output discarded, `|| true`.
- `scripts/ci/production-checks.sh`: `pulumi env run recipes-infrastructure/integration-tests-production` runs vitest, with `--reporter=json --outputFile`.
- It prints the pass/fail/skip counts and failing `fullName`s with `jq`; it never prints `failureMessages`.
- Auth0 checks already skip without `auth0ClientId`; CSRF checks post a wrong password (read-only).

### Seed

- `scripts/import-recipes.sh --session`: `read -rs` the `sessionid` from stdin (a hidden prompt on a TTY).
- It writes a Netscape cookie-jar line for the app host into `$work_dir`; the value never goes in `curl` args.
- It checks that `GET /admin/` with the session returns 200, else fails with "sign in again".
- It skips `admin_username`/`admin_password`/admin login, then reuses `csrf_token` and the upload as today.

### Trade-offs

- `protectData` on the runtime, not derived from `hostScheme`: it is explicit, and staging stays visibly opted out.
- The switches are on the runtime, not the identity output: only the container uses them.
- JSON reporter to a file plus masks: two layers, and failures still debuggable from the Pulumi update and a rerun.
- Separate CI scripts instead of inline `run:` blocks, so they can be unit-tested with stubbed commands.

## Implementation steps

### recipes-cms pull request (`Part of globz-eu/recipes-infrastructure#21`)

- C1, the switches in settings: `src/recipe_cms/settings/base.py`, `src/home/tests/test_settings_env.py`.
- C2, conditional URLs: `src/recipe_cms/urls.py`, new `src/home/tests/test_optional_urls.py`.
- C3, docs: `README.md` (production env vars), `CLAUDE.md` (Architecture: the switches).
- Run `uv run invoke format`, `uv run invoke lint`, `uv run invoke test`.
- Release after merge (by the user): `uv run invoke bump --part minor`, which gives v0.20.0.

### recipes-infrastructure pull request (`Closes #21`)

- I1, fail-safe local login (5 files):
  - `src/config/loadIdentityConfig.ts`, `Pulumi.staging.yaml` (`enableLocalLogin: "true"`).
  - `tests/unit/support/program.ts` (`stagingConfig`), `tests/unit/config-auth.test.ts`, `README.md` config table.
- I2, CMS switches (8 files):
  - New `src/config/readCmsSwitches.ts`; `src/config/stackConfig.ts`, `src/config/loadRuntimeConfig.ts`.
  - `src/app/productionEnv.ts`, `Pulumi.staging-runtime.yaml` (both `"true"`).
  - `tests/unit/support/program.ts` (`platformConfig`), new `tests/unit/program-runtime-cms-switches.test.ts`, `README.md`.
- I3, data protection (8 files):
  - New `src/dataProtection.ts`; `src/config/readPlatformSettings.ts`, `stackConfig.ts`, `src/database.ts`, `src/storage.ts`.
  - `Pulumi.staging-runtime.yaml` (`protectData: "false"`), `tests/unit/support/program.ts`.
  - New `tests/unit/program-runtime-protection.test.ts` (uses `recordResourceOptions`).
  - Also the `README.md` table; drop the `forceDestroy` risk bullet from `docs/environments.md` in I10.
- I4, switch outputs, live checks, dev compose (6 files):
  - `src/deploymentOutputs.ts`, `tests/integration/support/deployment.ts`, new `tests/integration/cms-switches.test.ts`.
  - Extend `program-runtime-cms-switches.test.ts`; `dev/compose.yml`, `tests/unit/dev-stack-compose-file.test.ts`.
- I5, production stack files and program test (5 files):
  - New `Pulumi.production.yaml`, `Pulumi.production-runtime.yaml`; `tests/unit/stack-files.test.ts`.
  - New `tests/unit/support/productionProgram.ts` (`runProductionProgram`, example.com fixtures).
  - New `tests/unit/program-production.test.ts`.
- I6, backups (3 files): `Pulumi.backups.yaml`, `.github/workflows/backup-check.yml` (schedule), `tests/unit/backup-check-workflow.test.ts`.
- I7, session seed (4 files):
  - `scripts/import-recipes.sh`, `tests/unit/support/runImportRecipes.ts` (stdin, `/admin/` stub, jar log).
  - New `tests/unit/import-recipes-session.test.ts`; `README.md` "Seeding a runtime stack".
- I8, CI scripts (6 files):
  - New `scripts/ci/mask-production-values.sh`, `scripts/deploy-production.sh`, `scripts/ci/production-checks.sh`.
  - New `tests/unit/mask-production-values.test.ts`, `deploy-production.test.ts`, `production-checks.test.ts`.
- I9, workflow (2 files): new `.github/workflows/production.yml`, `tests/unit/production-workflow.test.ts`.
- I10, docs (7 files):
  - `README.md` (Production section, CI), `CLAUDE.md` (six stacks, workflow, tests), `docs/environments.md`.
  - `docs/permissions.md` (production deployer and token), `docs/staging-bootstrap.md` (short "Production" section).
  - `.claude/rules/infrastructure.md` (image pin covers both runtime files), new `tests/unit/production-docs.test.ts`.
- Run `npm run lint`, `npm run typecheck`, `npm run test:unit` after each increment.
- If the recipes-cms release is not v0.20.0, update the pin in `Pulumi.production-runtime.yaml` before merging.

## Rollout (manual, by the user)

Agents run none of this. `gh` is a snap: pipe it through `cat`.

1. **recipes-cms:** merge the pull request; on `main` run `uv run invoke bump --part minor`, push the tag, wait for the image build.
2. **Scaleway:** bootstrap steps 1 and 2 with `name=recipes-production` and `recipes-deployer-production`; note project id and key.
3. **Zitadel (bootstrap 4b.3):** create org `recipes-cms-production`, make `pulumi-recipes` `ORG_OWNER`, note its id.
4. **DNS:** confirm the production zone is in the DNSimple account of the `dnsimple` environment.
5. **ESC:** write each file outside the repo, then `esc env init` and `esc env edit -f` (bootstrap step 5):

   ```yaml
   # scaleway-production-credentials: shape of scaleway-staging-credentials, production key and project
   # production-config
   values:
     pulumiConfig:
       baseDomain: <zone>
       appSubdomain: <app subdomain>
       enableCdn: "true"
       enableZitadel: "true"
       zitadelOrgId: "<recipes-cms-production org id>"
       zitadelEnforceMfa: "true"
       zitadelTestUserId: "<recipes-integration-tests user id>"
   # production-runtime-config
   values:
     pulumiConfig:
       identityStack: production
       projectId: "<recipes-production project id>"
       containerPort: "8000"
       scaleway:region: fr-par
       enableBackups: "true"
   ```

   ```bash
   for env in scaleway-production-credentials production-config production-runtime-config; do
     esc env init "globz-eu/recipes-infrastructure/$env"
     esc env edit "globz-eu/recipes-infrastructure/$env" -f "$ESC_DIR/$env.yaml"
   done
   ```

6. **Stacks:** `pulumi stack init globz-eu/production` and `pulumi stack init globz-eu/production-runtime` (no `up`).
7. **GitHub environment `production`:** main-only, then store a new `globz-eu` token with an expiry (e.g. `github-production-ci`):

   ```bash
   gh api -X PUT repos/globz-eu/recipes-infrastructure/environments/production \
     -F 'deployment_branch_policy[protected_branches]=false' \
     -F 'deployment_branch_policy[custom_branch_policies]=true' | cat
   gh api -X POST repos/globz-eu/recipes-infrastructure/environments/production/deployment-branch-policies -f name=main | cat
   gh secret set PULUMI_ACCESS_TOKEN --env production -R globz-eu/recipes-infrastructure
   ```

8. **Backups (bootstrap L4 to L6), from the pull-request branch:** `pulumi preview --stack backups`, then `pulumi up --stack backups`.
   - That creates `recipes-backups-production` and `backup-writer-production`.
   - L5: GitHub environment `backup-production`, with the reader key and the bucket/region variables.
   - L6: create `integration-tests-production` (`imports: [integration-tests]`, plus production's `BACKUP_READ_ACCESS_KEY`/`BACKUP_READ_SECRET_KEY`).
9. **Merge** the recipes-infrastructure pull request, then run `gh workflow run production.yml --ref main -R globz-eu/recipes-infrastructure | cat`.
   - Check the run's summary and both Pulumi update links.
   - Run the Staging workflow once (`deploy`) to show staging is unchanged.
10. **Seed once:** create the user in `recipes-cms-production`, grant `admin` (Project, then Authorizations), and sign in at `/admin/`.
    - Copy the `sessionid` cookie, then `STACK=production RUNTIME_STACK=production-runtime scripts/import-recipes.sh --session`.
    - Sign out afterwards.
11. **Backups check:** after the first 02:00 UTC run, `gh run list --workflow backup-check.yml -R globz-eu/recipes-infrastructure | cat`.
    - Optionally do L8 (a manual job run) and L9 (a restore exercise).

## Risks

- An older CMS image ignores `ENABLE_*`, which would expose the surfaces; the min-version test and live checks guard this.
- Flipping the `enableLocalLogin` default breaks any staging config that lacks it; I1 adds it in the same commit.
- `protect` makes production destroys and replacements fail until `pulumi state unprotect`; this is intended.
- The scheduled backup check fails if production's first nightly backup comes later than the merge.
- Masking is substring-based; a value missed by the key list could still leak, and `--suppress-outputs` plus file logs are the first layer.
- The shared test PAT can read the production org (viewer only); rotating it affects staging too.
- The seed overwrites by slug and locale; re-running it against edited production loses edits.
- Zitadel Free plan: 5,000 Management API requests are now shared by three orgs' runs.

## Open questions

- None. Resolved: the production zone is in the same DNSimple account, so `production-runtime` attaches `dnsimple` (user).
