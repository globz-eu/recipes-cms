# Publish the CMS image in fr-par (recipes-infrastructure issue #35, part 1 of 2)

## Why

- recipes-infrastructure issue #35: staging copies the CMS image from the build registry (nl-ams) into its own registry (fr-par) on every image change. It is slow and complex.
- Decision: recipes-cms publishes straight to a public namespace in fr-par, the staging region; staging runs that image without a mirror (part 2, recipes-infrastructure).
- The user's goal: less deploy complexity and time, image kept close to the environment, lower registry costs.

## Shared decisions (both repos)

- Namespace: `recipes-images`, public, region fr-par, Scaleway project "Home" (`9995ccc0-37a3-42dc-8a64-dd63fb88ead8`).
- Image: `rg.fr-par.scw.cloud/recipes-images/recipes-cms:vX.Y.Z`.
- First fr-par release: `v0.18.0` (next minor after v0.17.0).
- recipes-infrastructure creates the namespace with a script and later deletes the nl-ams namespace; this repo does neither.

## Goals

- `build.yml` pushes every tag, the arm64 digest, the multi-arch index and the build caches to the fr-par namespace only.
- Docs name the new image path.

## Non-goals

- No change to the build steps, multi-arch logic, release creation or e2e dispatch.
- No second push to nl-ams.
- No release here: `invoke bump` after merge is the user's step.

## Anti-goals

- A build that still depends on nl-ams.

## Changes

- `.github/workflows/build.yml`: `IMAGE` and the three `docker/login-action` `registry:` values point at fr-par. The `SCW_SECRET_KEY` secret stays (same organization, project "Home").
- README / CLAUDE.md / any doc naming `rg.nl-ams.scw.cloud/namespace-relaxed-faraday`: switch to the new path; say the namespace is created by recipes-infrastructure's script.
- Leave old plan docs under `docs/plans/` as they are.

## Constraints

- The namespace must exist before the first tag push; the PR description says so and links recipes-infrastructure's script.
- Link: `Part of globz-eu/recipes-infrastructure#35` (the recipes-infrastructure PR closes it).

## Left to the builder

- Wording of the docs; whether a test or lint guards the image path (none required).
