# Plan: code best-practices rules (recipes-cms #31)

Spec: [code-best-practices-rules.spec.md](code-best-practices-rules.spec.md). Decisions there are final.

## Context and goal

- Issue #31: adapt sibling clean-code rules (recipes-infrastructure PR #19, recipes-frontend PR #14) to Python.
- Add `.claude/rules/code-quality.md`; ruff enforces Pythonic rules, mypy checks types.
- Behaviour-neutral: `invoke test` keeps the same test count.
- Base: recipes-cms branch `feature/dev-frontend-origins`-era `main`; first commit "Add plan for code-best-practices-rules" is outside this plan.

## Measurements

- Pythonic sets: 16 findings (9 B904, 3 RET501, 1 B018, 1 C901, 1 RET505, 1 UP035).
- Production `ANN` (excl. tests, migrations; incl. `tasks.py`): 109 findings.
- Per area: `home` 37, `oidc_auth` 26, `tasks.py` 25, `recipes` 12, `recipe_cms` 5, `image_auth` 3, `manage.py` 1.
- 15 of them `ANN401`: social-auth `backend`/`strategy` and `*args`/`**kwargs` in `oidc_auth/pipeline.py`, `providers.py`.
- `max-args = 3` would flag 8 sites, `5` (ruff default) only `tasks.py:92` (invoke CLI flags).

## Acceptance criteria

1. `uv run invoke lint` runs `ruff check`, `ruff format --check`, `mypy`; exits 0.
2. Ruff selects `C4,SIM,UP,RET,PERF,B,PIE,PTH,FURB,C901,PLR0912,PLR0913,ANN` plus existing sets.
3. `target-version = "py314"`; `C901` max-complexity 10.
4. `ANN` ignored in `**/tests/**` and `**/migrations/**`; other new sets ignored in migrations.
5. mypy type-checks all of `src/` and `tasks.py` with `django-stubs` and `djangorestframework-stubs`.
6. Untyped libraries use per-module `ignore_missing_imports`; no blanket ignore.
7. Every `noqa` / `type: ignore` has a code and a reason.
8. `invoke test` passes with the same test count as before.
9. `.claude/rules/code-quality.md` has all 13 spec sections with repo examples.
10. `backend.md` and `code-quality.md` share no rules; `CLAUDE.md` links both, lists `invoke lint`, new commit style.
11. Dev dependencies only in the `dev` group; `uv.lock` updated.

## Design

### Tooling

- `pyproject.toml`: add `mypy`, `django-stubs`, `djangorestframework-stubs` to the `dev` group.
- `[tool.ruff]`: `target-version = "py314"`; extend `select`; `[tool.ruff.lint.mccabe] max-complexity = 10`.
- `[tool.ruff.lint.pylint]`: `max-args = 5` (ruff default), `max-branches = 12`; ≤ 3 params stays written guidance (spec).
- `tasks.py` `worktree_env` keeps its CLI-flag parameters: `# noqa: PLR0913` with reason.
- `[tool.ruff.lint.flake8-annotations]`: `allow-star-arg-any = true` (Django/social-auth `*args`/`**kwargs`).
- Social-auth `backend`/`strategy`: annotate with `social_core` classes where importable; else `Any` with `# noqa: ANN401` and reason.
- `per-file-ignores`: `**/tests/**` and `**/migrations/**` skip `ANN`; migrations skip new sets.
- `[tool.mypy]`: `plugins = mypy_django_plugin.main, mypy_drf_plugin.main`; `python_version = "3.14"`.
- `[tool.django-stubs]`: `django_settings_module = "recipe_cms.settings.dev"`.
- `disallow_untyped_defs` on via override for non-test modules; off for `*.tests.*`.
- Overrides `ignore_missing_imports` for `wagtail.*`, `social_core.*`, `social_django.*`, `modelcluster.*`, `storages.*`, `wagtail_storages.*`, `invoke.*`.
- `tasks.py`: add `lint` task running `ruff check`, `ruff format --check`, `mypy` on host; env `AUTH_PROVIDERS=local`.
- `tasks.py` `format` also covers `tasks.py`.

### Rules docs

- `.claude/rules/code-quality.md`: sections Simplicity/YAGNI, DRY, Separation of concerns, Size limits, Modularity, Naming, Pythonic code, Comments, Types, Testing, Before finishing, Workflow, Committing changes.
- Examples: `recipes/importer.py` (service split), `home/worktree_env.py` (pure helpers), `oidc_auth/pipeline.py`.
- Size limits (files ≤ 200, functions ≤ 60, ≤ 3 params, nesting ≤ 3) marked guidance, not enforced.
- Front matter `paths: ["src/**/*.py", "tasks.py"]`.
- `backend.md`: drop line 15's format sentence (moves to Before finishing); keep Django/Wagtail only.
- `CLAUDE.md`: Commands gets `invoke lint`; Conventions links both rules, states commit style.

## Implementation steps

### Increment 1: tooling

1. `Add ruff Pythonic rule sets` — `pyproject.toml` (config only, rules listed); record baseline findings and `ANN` count.
2. `Add mypy with Django stubs` — `pyproject.toml`, `uv.lock`; config and overrides, record error count.
3. `Add invoke lint task` — `tasks.py`; `format` includes `tasks.py`.

### Increment 2: existing findings

4. `Fix ruff findings in oidc_auth` — B904 `raise … from`, etc.; list files from step 1.
5. `Fix ruff findings in home, recipes and image_auth` — RET501/RET505/B018/UP035/C901 sites.
6. `Fix remaining ruff findings` — only if any left (e.g. `tasks.py`); else skip.

### Increment 3: annotations and mypy, per app

7. `Annotate oidc_auth` — ~11 files; fix mypy errors there.
8. `Annotate home` — models, views, locales, `worktree_env.py`, commands.
9. `Annotate recipes` — `importer.py`, `serializers.py`, `views.py`, command.
10. `Annotate image_auth and recipe_cms` — `views.py`, `middleware.py`, `settings/base.py`, `manage.py`.
11. `Annotate tasks.py` — `tasks.py` only; enable `ANN` repo-wide, `invoke lint` fully green.
12. If a step exceeds 8 files, split by module and keep one commit per app group.

### Increment 4: rules docs

13. `Add code quality rules` — `.claude/rules/code-quality.md`.
14. `Trim backend rules` — `.claude/rules/backend.md`.
15. `Document lint and commit style` — `CLAUDE.md` and README task list.

## Verification

- After each step: `/snap/astral-uv/current/bin/uv run invoke format` (or `uv run … 2>&1 | cat`).
- Lint: `uv run invoke lint 2>&1 | cat` must exit 0 from step 11.
- Tests: `uv run invoke dev` in the stack, then `uv run invoke test`; compare test count with baseline.
- Stop the stack afterwards: stop watch, `uv run invoke down`.
- Check `git grep -nE "noqa|type: ignore"` entries all carry code and reason.

## Risks

- mypy error count is unmeasured; step 2 baseline may resize increment 3.
- mypy plugin needs settings importable on host; dummy env vars may be required for `recipe_cms.settings.dev`.
- Python 3.14 support in `django-stubs` / mypy versions; pick latest and verify.
- `target-version` bump may trigger new `UP` fixes in files outside the finding list.
- Annotations on DRF/Wagtail overrides can clash with untyped parents; use `Any` sparingly with reason.
- Max-args 3 flags Django signatures (`request, *args, **kwargs`); per-site `noqa` count may grow.

## Decisions on open questions

- `max-branches = 12` (ruff default), user.
- README lists `invoke lint` next to the other invoke tasks, user.
