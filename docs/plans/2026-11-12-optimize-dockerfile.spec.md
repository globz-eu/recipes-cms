# Spec: optimize the Dockerfile (recipes-cms #6)

Sibling spec: recipes-infrastructure `docs/plans/2026-11-12-plain-cms-commands.spec.md` (switches its in-image commands away from `uv`).

## Why

- Release builds take 6–50 min (`build.yml` runs, v0.13.0–v0.16.0); arm64 is emulated with QEMU, with no layer cache.
- The runtime image carries build tools, `-dev` headers, `ffmpeg`, `uv` and the `dev` dependency group.
- `COPY ./src` comes before `uv sync`, so any code change reinstalls all dependencies.

## Goals

- Multi-stage `Dockerfile`: a build stage builds everything; the final stage only copies results in.
- Build stage: `uv sync --locked --no-dev --compile-bytecode` into a venv, then `collectstatic` (`AUTH_PROVIDERS=local`).
- Layer order for caching: install deps from `pyproject.toml` + `uv.lock` before copying `src/`.
- Final stage: Python, the venv, app code and collected static only; no `uv`, compilers, `-dev` packages or `ffmpeg`.
- Final stage keeps: non-root `wagtail` user, `/app/media/{images,original_images}`, `DJANGO_SETTINGS_MODULE` build arg, port 8000, `HEALTHCHECK` on `/health`.
- Venv on `PATH`, so `python manage.py …` and `gunicorn …` work in `/app`; default `CMD` is `gunicorn recipe_cms.wsgi:application`.
- recipes-cms callers switch to plain commands: `compose.dev.yml`, `tasks.py` (`test --postgres`), README/CLAUDE.md.
- `uv run invoke test --postgres` still passes in the new image (it has no `dev` group, so `invoke` is missing).

### CI (`build.yml`)

- Native per-arch jobs: amd64 on `ubuntu-latest`, arm64 on `ubuntu-24.04-arm`; no QEMU.
- Layer cache per arch (e.g. GitHub Actions cache).
- amd64 job pushes `vX.Y.Z` and triggers the recipes-infrastructure e2e dispatch without waiting for arm64.
- arm64 job then rewrites `vX.Y.Z` as a multi-arch index: the existing amd64 digest plus its arm64 image.
- An arm64 failure never blocks staging or the e2e dispatch.

### Merge order (user approved; stated in both PRs)

1. Merge this recipes-cms PR, without tagging.
2. Merge the recipes-infrastructure PR.
3. Tag the recipes-cms release right away; its e2e run uses new commands and new image.

- The dev stack can't start the previous release for those few minutes; accepted.
- This PR says `Part of #6`; the recipes-infrastructure PR (merged last) closes #6.

## Non-goals

- Changing the app, its dependencies or Python version (3.14).
- Changing how staging deploys or mirrors the image.
- Editing recipes-infrastructure (the sibling spec covers it).

## Anti-goals

- A final image that still runs `uv` or can only start through it.
- Staging releases waiting on, or failing because of, the arm64 build.

## Success

- PR states image size and a release build time before/after (amd64 and arm64).
- A code-only rebuild reuses the dependency layer.

## Calls made by Claude

- Base both stages on `python:3.14-slim-trixie` (system Python on `PATH`, replaces uv-managed Python).
- Drop `ffmpeg`: nothing in `src/` uses it.
- Drop `curl` from the final stage if the healthcheck can use Python instead.
- `vX.Y.Z` is briefly amd64-only until the arm64 job finishes (user chose this).
- The window doesn't affect staging: it needs amd64, and the mirror runs on an amd64 host.
- arm64 job failure: recover with "Re-run failed jobs"; no extra `workflow_dispatch`.
- The index rewrite uses the amd64 job's digest output, not the tag's current value, so re-runs are safe.

## Left to the builder

- Exact venv path, `UV_*` env vars, BuildKit cache mounts.
- Which system packages the build stage needs, and which runtime libs the final stage still needs.
- How `test_tasks.py` skips cleanly when `invoke` is absent.
- Action versions, cache backend and job/step names in `build.yml`.
