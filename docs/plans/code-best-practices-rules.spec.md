# Spec: code best-practices rules (recipes-cms #31)

Adapts the clean-code rules of recipes-infrastructure (PR #19) and recipes-frontend (PR #14) to this Django/Wagtail stack, with a lighter touch.

### Intent

- Agents write clean, simple, modular, Pythonic, typed code here without being told each time (issue #31).
- Ruff and mypy check what they can; the rest is written guidance.

### Goals

- New `.claude/rules/code-quality.md`, with examples from this repo (e.g. `recipes/importer.py`, `home/worktree_env.py`, `oidc_auth/pipeline.py`).
- Sections: Simplicity/YAGNI, DRY, Separation of concerns, Size limits, Modularity, Naming, Pythonic code, Comments, Types, Testing, Before finishing, Workflow, Committing changes.
- Pythonic section: comprehensions over append loops, `any`/`all`, `enumerate`/`zip`, f-strings, `pathlib`, context managers, `raise … from`, early returns, no mutable defaults, `dict.get`, unpacking.
- `.claude/rules/backend.md` keeps only Django/Wagtail rules; no overlap with `code-quality.md`.
- Ruff enforces the Pythonic rule sets: `C4`, `SIM`, `UP`, `RET`, `PERF`, `B`, `PTH`, `FURB`, plus `C901` (≤ 10), max args, max branches.
- Production code fully annotated, enforced by ruff `ANN`.
- mypy with `django-stubs` and `djangorestframework-stubs` type-checks all of `src/`.
- `uv run invoke lint` runs `ruff check`, `ruff format --check` and mypy; all pass on the branch.

### Decisions (user)

- Lighter touch: size limits (files ≤ 200 lines, functions ≤ 60, ≤ 3 params, nesting ≤ 3) are written guidance, not enforced.
- Existing oversized files are not split.
- Ruff enforces the Pythonic rules; existing findings (16 today) are fixed in this change.
- Code uses typing and is type-checked.
- Annotations required in production code only; tests and migrations exempt from `ANN`.
- Commit style switches to the siblings': capitalised imperative verb, short, no prefix.

### Decisions (my calls)

- Type checker: mypy + `django-stubs` + `djangorestframework-stubs` (most mature Django support).
- Untyped libraries (Wagtail, social-auth, modelcluster, storages, invoke) handled via `ignore_missing_imports` per module.
- mypy checks tests too, but they need no annotations (untyped defs not required there).
- Ruff argument limit allows Django/DRF signatures we don't control (`request, *args, **kwargs`, overridden methods).
- `noqa` / `type: ignore` only for code we don't control, with a code and a reason.
- Before finishing: `invoke format`, `invoke lint`, `invoke test`.
- `CLAUDE.md`: link both rules files, add `invoke lint`, new commit style.
- CI unchanged (it only builds images on tags).
- `invoke lint` runs on the host via `uv run` (no Docker needed); mypy loads `recipe_cms.settings.dev` with `AUTH_PROVIDERS=local` and dummy env vars as needed.
- Ruff `target-version` raised to `py314` to match `requires-python`.
- Migrations excluded from the new ruff rule sets.
- `tasks.py` covered by ruff (incl. `ANN`) and mypy.

### Constraints

- Behaviour-neutral: `invoke test` stays green with the same test count.
- `tasks.py` is linted like `src/` (it is production tooling).
- New dev deps only in the `dev` group of `pyproject.toml`, `uv.lock` updated.

### Non-goals

- Splitting files or functions to meet the size limits.
- Annotating tests or migrations.
- Adding a CI lint job.
- Pydantic or other runtime validation libraries.

### Left to the builder

- Exact ruff rule codes and options (e.g. `PLR0913` vs. relying on `C901`), and mypy strictness flags.
- How each existing finding and mypy error is fixed.
- Which repo examples illustrate each rule.
