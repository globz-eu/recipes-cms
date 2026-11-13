# Plan: optimize the Dockerfile (recipes-cms #6)

Spec: `docs/plans/2026-11-12-optimize-dockerfile.spec.md`. PR says `Part of #6`.

## Goal

- Smaller image, cached dependency layer, native per-arch CI builds; no `uv` in the image.

## Acceptance criteria

1. Final image has no `uv`, `gcc`, `ffmpeg`, `curl`, `-dev` packages or `dev` group.
2. `docker run IMAGE python manage.py check` and default `gunicorn` CMD work in `/app`.
3. Pillow JPEG/WebP and `psycopg2` import in the final image.
4. `HEALTHCHECK` turns healthy via Python against `/health`.
5. Runs as `wagtail`; `/app/media/{images,original_images}` and `/app/static` exist.
6. Code-only rebuild shows the `uv sync` step `CACHED`.
7. `uv run invoke test --postgres` passes; `home.tests.test_tasks` is skipped in-container.
8. `build.yml`: amd64 tag push and e2e dispatch never wait on arm64.
9. No `uv run` against the container left in `compose.dev.yml`, `tasks.py`, README, CLAUDE.md.

## Builder decisions

- Base: `python:3.14-slim-trixie` for both stages.
- Venv `/opt/venv` (outside `/app`, so watch sync never touches it); `PATH=/opt/venv/bin:$PATH`.
- Build env: `UV_PROJECT_ENVIRONMENT=/opt/venv`, `UV_PYTHON_DOWNLOADS=never`, `UV_LINK_MODE=copy`, `UV_COMPILE_BYTECODE=1`.
- `uv sync --locked --no-dev --no-install-project` with `--mount=type=cache,target=/root/.cache/uv`.
- No apt packages: Pillow and `psycopg2-binary` ship wheels with bundled libs.
- Add `build-essential`/`-dev` to the build stage only if `uv sync` needs a source build.
- Drop obsolete `mkdir recipe_cms/static` (`STATICFILES_DIRS` empty, `settings/base.py:276`).
- CI cache: registry cache `recipes-cms:buildcache-<arch>`; GHA cache is ref-scoped, each tag is a new ref.
- Registry cache tags are not semver, so `dev-stack.sh:225` lookup ignores them.

## Implementation steps

1. `.dockerignore`: add `.venv/` (shrinks build context).
2. `src/home/tests/test_tasks.py`: wrap `invoke` imports in `try`/`except ImportError: raise SkipTest(...) from None`.
3. Multi-stage switch, one commit so the dev stack never breaks:
   - `Dockerfile`: build stage copies `pyproject.toml`, `uv.lock`, `.python-version`, syncs, then `COPY src`, `collectstatic` (`AUTH_PROVIDERS=local`).
   - Final stage: `useradd wagtail`, media dirs, `COPY --from=build` venv and `/app/static`, `COPY --chown=wagtail src`.
   - `HEALTHCHECK CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]`.
   - `CMD ["gunicorn", "recipe_cms.wsgi:application"]` (binds `0.0.0.0:$PORT`).
   - `compose.dev.yml:23-26`: `python manage.py …`.
   - `tasks.py:127`: `python manage.py test`; `test_tasks.py:188` assertion likewise.
4. Docs: README lines 216-218, 232, 356, 444 and CLAUDE.md lines 32-33 to `python manage.py`.
5. CLAUDE.md "Deployment notes": one bullet on image layout (venv on `PATH`, no `uv`).
6. `.github/workflows/build.yml`: drop QEMU; job `amd64` on `ubuntu-latest` pushes `vX.Y.Z`, outputs digest, creates release, dispatches e2e.
7. `build.yml`: job `arm64` on `ubuntu-24.04-arm` pushes by digest (`push-by-digest=true`) in parallel.
8. `build.yml`: job `multi-arch` (`needs: [amd64, arm64]`) runs `docker buildx imagetools create` from both digest outputs.

## Testing / verification

- `uv run invoke format`, `uv run invoke lint`, `uv run invoke test`.
- Size: build `main` and branch locally per arch; `docker image inspect -f '{{.Size}}'`.
- Compressed size: `docker buildx imagetools inspect …:v0.16.0` versus new tag.
- Build time before: `gh run list --workflow build.yml --json … | cat` (v0.13.0-v0.16.0).
- Local time: `time docker buildx build --no-cache --platform linux/amd64` on `main` and branch.
- Cache: edit a file in `src/`, rebuild with `--progress=plain`, confirm `uv sync` `CACHED`.
- Image checks: `docker run --rm IMAGE sh -c 'command -v uv gcc ffmpeg curl'` prints nothing.
- `python -c "from PIL import features; assert features.check('jpg') and features.check('webp')"`.
- Worktree: `git worktree add`, `$DEV_STACK env --port 8091`, set `RECIPES_INFRA_DIR`.
- There: `uv run invoke test --postgres`, `uv run invoke dev` until healthy, then `uv run invoke down --volumes`.

## Risks

- arm64 failure leaves `vX.Y.Z` amd64-only until "Re-run failed jobs" (accepted).
- Registry cache adds storage to the Scaleway namespace.
- A future dependency without wheels needs compilers back in the build stage.
- `collectstatic --clear` at runtime needs `/app/static` writable by `wagtail`.

## Decisions (user, at plan approval)

- PR states local `--no-cache` build times; real CI times follow after the tag build (PR follow-up note).
- Registry cache tags `recipes-cms:buildcache-amd64`/`-arm64` stay in `namespace-relaxed-faraday`.
- Separate `multi-arch` job approved.

## Merge order (stated in the PR)

1. Merge this recipes-cms PR, without tagging.
2. Merge the recipes-infrastructure PR (closes #6).
3. Tag the recipes-cms release.
4. Follow-up recipes-infrastructure PR bumps `containerImage` in `Pulumi.staging.yaml`; staging jobs (`src/app/createJobRuns.ts`) switch to `python manage.py`.
