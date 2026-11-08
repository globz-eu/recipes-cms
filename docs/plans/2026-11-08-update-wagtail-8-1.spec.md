# Spec: update Wagtail to 8.1 and refresh all dependencies (recipes-cms #17)

Stay current; no new features.

## Goals

- Wagtail 7.3 → 8.1 (newest release; issue asked for 8.0 "or newer").
- Refresh every dependency in `uv.lock` to its latest compatible version (`uv lock --upgrade`), incl. Django 6.0.2 → 6.1.x, DRF, social-auth, ruff, mypy, stubs.
- Raise `pyproject.toml` lower bounds to the versions now locked; add `django>=6.1` explicitly.
- Adapt code to anything the upgrades break or deprecate (Wagtail 8.0/8.1 and Django 6.1 release notes).
- Fix new ruff/mypy findings from the newer tools; format-only changes in their own commit.
- Commit any migrations Wagtail or Django generate (`makemigrations --check` clean).
- Release after merge: `uv run invoke bump --part minor` on `main` (0.14.0 → 0.15.0), push commit and tag.
- User merges the PR, then asks Claude to run the release; not part of the PR or plan tasks.

## Non-goals

- New Wagtail features (v3 API, custom base page models, `MAILERS`).
- Python version change (stays 3.14).
- Migrating off any API Wagtail only deprecates for later (e.g. v2 API, not used here).

## Findings so far

- Code uses none of the Wagtail 8.0/8.1 removed APIs or settings.
- `WAGTAILSEARCH_BACKENDS` has no `INDEX` option; API serves no image renditions (AVIF/WebP change irrelevant).
- Wagtail 8.1 pulls in new transitive deps `django-ninja` and `django-tasks`.

## Acceptance

- `uv run invoke lint`, `uv run invoke test` and `uv run invoke test --postgres` pass.
- No new deprecation warnings from our code in the test run (`-W` output checked).
- Dev stack (`uv run invoke dev`) smoke test: admin login, recipe edit/publish, `/api/` recipe list, bulk upload, media serving.
- Docker image builds (`uv run invoke dev --build`).

## Calls made by Claude

- Target 8.1, not 8.0 (user: "if newer, use it").
- Minor version bump for the release.
- Release runs after merge on `main`, matching earlier releases (e.g. `f7f4a16 0.14.0`).
- A package that blocks Wagtail 8.1 or Django 6.1: stop and report, don't hold back the target.
- Other packages: whatever `uv lock --upgrade` resolves, incl. new majors; adapt code if needed.
- Deprecation check: run tests with `python -Wd` and read the output; no `-W error` in the test task.
- "Our code": warnings whose stack points into `src/`, or caused by our settings.
- Baseline: run lint and both test suites on `main` first; pre-existing failures are recorded, not fixed.
- Check whether `django-tasks`/`django-ninja` need settings, `INSTALLED_APPS` or tables; add only what's required.
- Image check: `invoke dev --build` is enough; production settings don't change.

## Left to the builder

- Exact upgrade command order and how to split commits (lock refresh, bounds, code fixes).
- Whether a deprecation in third-party code needs a filter or just a note.
