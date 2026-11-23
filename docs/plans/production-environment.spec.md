# Spec: production environment (recipes-infrastructure issue #21, last step)

Closes [recipes-infrastructure issue #21](https://github.com/globz-eu/recipes-infrastructure/issues/21) and unblocks making the repo public ([recipes-infrastructure issue #26](https://github.com/globz-eu/recipes-infrastructure/issues/26)).

## Why

- Production becomes the one place recipes are written; staging stays throwaway and e2e-only.
- The repo goes public: nothing committed may identify production (domain, project, org, users).
- Production faces the public: no developer surfaces (DRF browsable API, Django admin).

## Delivery

- **recipes-cms pull request** (`Part of globz-eu/recipes-infrastructure#21`): switches for the browsable API and the Django admin, then a release (`invoke bump`).
- **recipes-infrastructure pull request** (`Closes #21`): stacks, workflow, seed, backups, docs; pins the new recipes-cms release.

## Goals

1. **Stacks** `production` (identity) and `production-runtime`, same program, fixed hosts (`<appSubdomain>.<baseDomain>`, `static.<app host>`), never destroyed by CI.
2. **Nothing identifying committed:** `Pulumi.production.yaml` holds only its ESC environment list; `Pulumi.production-runtime.yaml` holds the environment list plus `containerImage` and `frontendVersion` (a release stays a reviewed commit).
   - Everything else (domain, app subdomain, sign-in choice, project id, Zitadel org id, test user id, region if needed) comes from ESC `pulumiConfig`.
   - A unit test fails if either file holds anything else.
3. **Zitadel only:** no local login, no Auth0, no `adminUsername`, no ensure-admin job; admins come from the Zitadel `admin` role.
   - Own Zitadel org `recipes-cms-production`, made by hand.
4. **Production data is protected:** the production database and media bucket get Pulumi `protect`, and the media bucket has no `forceDestroy` (staging keeps both as today, URNs unchanged).
   - A destroy refuses until someone deliberately unprotects them; backups remain the real safety net.
5. **No DRF browsable API on production:** `/api/` answers JSON only; `/api-auth/` (the browsable API's login/logout) is not mounted.
6. **No Django admin on production:** `/django-admin/` is not mounted; the Wagtail admin `/admin/` stays (editors write recipes there).
   - With `/api-auth/` off, `LOGIN_URL` (today `/api-auth/login/`) points at the Wagtail login; no URL reverses a removed name.
6a. **Fail-safe defaults:** a key missing from ESC must not open production.
   - In the infra program, `enableLocalLogin` and the two CMS switches default to off; staging and dev set them on explicitly in their committed files.
7. **One-time seed from recipes-data:** `scripts/import-recipes.sh` gains a way to use a Zitadel browser session instead of the local admin login.
   - The user signs in to production's Wagtail admin through Zitadel as an `admin`-role user, then gives the script the `sessionid` cookie at a hidden prompt (never an argument, never printed).
   - The script fetches a CSRF token with that session and posts `../recipes-data/recipes.json` to the bulk-upload API, as on staging.
   - Run once by hand on an empty production; afterwards the Wagtail admin is the source of truth, and nothing re-runs the seed.
8. **Backups:** production joins `backedUpStacks` and the check workflow (with its `schedule`), and `production-runtime` sets `enableBackups` and attaches `backup-writer-production`.
9. **Manual "Production" workflow, the only way to deploy production (auditable, no local deploys):** `workflow_dispatch`, deploy only (identity then runtime), `main` only, GitHub environment `production` (main-only deployment branches), own `PULUMI_ACCESS_TOKEN`; runs the read-only integration checks, never e2e.
   - Public logs reveal nothing: `pulumi up` output goes to a file that is never uploaded; the log shows the result and the Pulumi update link only.
   - Audit trail: the GitHub run (who, which commit) plus Pulumi Cloud's private update history, each update tagged with the run URL and commit (`pulumi up --message`).
   - Second layer: the workflow reads the production values from ESC and masks them with `::add-mask::` before any other step.
   - The integration checks print a summary only (no URLs in failure output).
10. **Docs:** one-time setup as shared steps plus a short production section (not a copy of the staging bootstrap); README, CLAUDE.md, `docs/environments.md` updated; the rollout steps below.

## Non-goals

- Making staging config secret (staging is throwaway and stays readable).
- History rewrite and the other recipes-infrastructure issue #26 items.
- Continuous sync of recipes-data into production.
- Auth0 on production.

## Anti-goals

- Never commit a production domain, project id, org id or user id (also not in comments, docs or test fixtures).
- Never let CI destroy a production stack, nor run e2e (writes data) against it.
- Never re-run the seed automatically: the importer overwrites recipes matched by slug and locale.
- Never declare an identity resource in the runtime stack.
- Never print the session cookie or the production config values in a CI log.
- Never deploy production from a workstation; docs describe only the workflow.

## Constraints

- All hostnames through `src/urls.ts`; resource logical names of staging unchanged (no URN changes).
- Agents never run `pulumi up`/`destroy` or `esc env set` on live stacks; the user does the rollout.
- Integration checks on production are read-only; checks that need local login or Auth0 skip there.
- CI on the free Pulumi plan: personal token as environment secret, as staging.
- recipes-cms: staging and dev behaviour unchanged unless the switch is set.

## Approaches considered

- **Where the versions live:** ESC (strictly only environments) or the runtime stack file. **Picked: stack file** (user): not identifying, and a release stays a reviewed commit.
- **Seeding:** sign in through Zitadel and reuse `import-recipes.sh` with the browser session; or a one-off Serverless Job with the JSON as a mounted secret (more moving parts, 59.5 KB near Secret Manager's 64 KiB limit). **Picked: Zitadel session** (user).
- **Deploying:** quiet CI deploy with masks (picked: auditable), local deploy only (ruled out by the user: not auditable), CI job printing nothing at all (hard to debug, no audit link).
- **Data protection:** `protect` on the production database and media bucket (picked, user).
- **Seed cadence:** one-time, then the Wagtail admin is the source (user). A Pulumi-managed seed job was ruled out: a redeploy could re-run it.

## Rollout (manual, by the user)

1. Merge the recipes-cms pull request and release it.
2. Create the hand-made pieces: Scaleway project and deployer, Zitadel org `recipes-cms-production`, DNS zone/record access, ESC environments (`production-config` and whatever the plan names), GitHub environment `production` with its token.
3. Deploy the `backups` stack with `production` in `backedUpStacks` (creates `backup-writer-production`).
4. Merge the recipes-infrastructure pull request; run the Production workflow.
5. Grant the `admin` role in Zitadel, sign in, run the seed once.
6. Check the first nightly backup and the backup-check run.

## Calls made by Claude (correct if wrong)

- "Django admin" means `/django-admin/` only; the Wagtail admin stays.
- Turning off the browsable API also removes `/api-auth/`.
- The recipes-cms switches default to today's behaviour (on); only production sets them off, so staging, dev and the e2e suite are unaffected.
- The runtime file keeps exactly `containerImage` and `frontendVersion`; `containerPort`, `region` and `identityStack` come from ESC or defaults (the plan picks).
- The seed reuses `import-recipes.sh` rather than a new script.
- Fail-safe defaults (goal 6a) instead of a separate production stack kind.
- `LOGIN_URL` points at the Wagtail login when `/api-auth/` is off.
- Production sizing (scale-to-zero, DB capacity, CDN) equals staging's; different sizing is out of scope.

## Left to the builder

- Names and form of the recipes-cms switches (env vars read in settings; URLs mounted conditionally) and their tests.
- How production integration checks get their credentials (own ESC environment or the shared one) and which checks skip.
- Name and layout of the production ESC environments and the unit test enforcing the stack files.
- How the workflow keeps production values out of logs (`--suppress-outputs`, masking).
- How `forceDestroy` is switched per stack (config key or stack kind).
- Whether the workflow calls a `scripts/deploy-production.sh` (CI-only, quiet) or `pulumi up` directly.
- How `protect` is switched per stack without changing staging's resources.
