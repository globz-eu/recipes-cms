# Plan: publish the CMS image in fr-par

Spec: `docs/plans/2026-11-13-publish-image-fr-par.spec.md`.
Part of globz-eu/recipes-infrastructure#35 (part 1 of 2).

## Context and goal

- `build.yml` pushes to `rg.nl-ams.scw.cloud/namespace-relaxed-faraday/recipes-cms`.
- Staging (fr-par) mirrors it on every image change; part 2 drops that mirror.
- Goal: CI publishes straight to `rg.fr-par.scw.cloud/recipes-images/recipes-cms`.
- Only reference found outside old plans: `.github/workflows/build.yml:9,28,84,111`.
- README and CLAUDE.md name no registry path today.
- Old plans (`2026-11-12-optimize-dockerfile.plan.md:73`, its `.html` files) stay unchanged.

## Acceptance criteria

1. `build.yml` `env.IMAGE` is `rg.fr-par.scw.cloud/recipes-images/recipes-cms`.
2. All three `docker/login-action` steps use `registry: rg.fr-par.scw.cloud`.
3. `SCW_SECRET_KEY`, build steps, caches, release and dispatch steps are otherwise unchanged.
4. `grep -rn 'nl-ams\|relaxed-faraday' --exclude-dir=docs .` returns nothing.
5. README "Deployment" names the image path and says recipes-infrastructure's script creates the namespace.
6. CLAUDE.md "Deployment notes" names the image path in the existing `build.yml` sentence.
7. `uv run invoke lint` and `uv run invoke test` pass.

## Design

- Only change the values; job structure stays as in `build.yml` (spec non-goals).
- Cache refs follow `env.IMAGE`, so `buildcache-amd64`/`-arm64` move with it automatically.
- The new namespace starts with no cache, so the first fr-par build is a cold build.
- No test or lint guard for the image path (spec leaves it optional; YAGNI).
- Docs: one sentence each, linking recipes-infrastructure's namespace script.

## Implementation steps

1. `build.yml:9`: set `IMAGE` to the fr-par path.
2. `build.yml:28,84,111`: set `registry:` to `rg.fr-par.scw.cloud` (same commit as step 1).
3. `README.md:395-397`: add the image path and namespace-script sentence.
4. `CLAUDE.md:61`: add the image path to "Images are built by GitHub Actions...".
5. PR description: namespace must exist before the first tag push; link the script.
6. PR description: `Part of globz-eu/recipes-infrastructure#35`.

## Verification

- `actionlint .github/workflows/build.yml` if installed.
- Otherwise `uv run python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" .github/workflows/build.yml`.
- Acceptance criterion 4's grep.
- `git diff main -- .github/workflows/build.yml` shows only the four value lines.
- `uv run invoke lint 2>&1 | cat` and `uv run invoke test 2>&1 | cat` (no Python change; sanity only).
- Real check happens on the user's `v0.18.0` tag push (out of scope).

## Risks

- Tag pushed before the namespace exists: all push steps fail.
- `SCW_SECRET_KEY` may lack registry write on project "Home" namespaces.
- recipes-infrastructure's `dev-stack.sh` lookup still targets nl-ams until part 2 merges.

## Open questions

- Path or name of recipes-infrastructure's namespace script (spec gives none); needed for doc links.
- Which project/permissions the `SCW_SECRET_KEY` API key has; can it push to `recipes-images`?
- Is `pyyaml` available in the dev group for the fallback YAML check, or is actionlint preferred?
