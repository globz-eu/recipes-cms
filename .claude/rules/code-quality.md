# Clean, simple, modular code

These rules apply to every change. Ruff and mypy enforce the measurable ones (`uv run invoke
lint`). Don't silence a finding to get past it. Restructure the code instead. `noqa` and
`type: ignore` need a code and a reason: `# noqa: PLR0913 -- parameters are invoke CLI flags`,
`# type: ignore[attr-defined]  # reverse accessor added by social_django`. Use them only for code
you don't control (a Django/DRF override, an untyped library) or a deliberate convention (star
imports in the settings modules), never to get past a finding. mypy's
`warn_unused_ignores` flags an ignore that is no longer needed, so remove it then.
Django/Wagtail-specific rules are in `backend.md`.

## Simplicity / YAGNI

- Write the simplest code that solves the current requirement. No speculative settings, options,
  extension points or abstractions "for later".
- Don't add a dependency for something a few lines of code can do.
- Prefer pure functions. Keep side effects (database, network, files, subprocesses, the clock) at
  the edges: `home/worktree_env.py` holds pure helpers (`default_postgres_port`, `rewrite_env`),
  `tasks.py` does the file and Docker work.
- Don't reassign parameters. Return new values.

## DRY

- Extract a helper on the second real use, or earlier when a name explains the logic better than
  the code does. `_load_homepages` (`recipes/importer.py`) is the one place that resolves the
  HomePage per locale.
- Similar-looking code with different reasons to change is not duplication. Don't merge it.

## Separation of concerns

- Views and serializers handle HTTP and validation; business logic lives in services that don't
  know about requests: `recipes/importer.py` serves both the API view and the `import_recipes`
  command.
- Management commands and tasks parse arguments and delegate.
- Validate untrusted input at the boundary (DRF serializers, `home.locales.get_requested_locale`),
  not deeper in.

## Size limits

- Guidance, not enforced: files ≤ 200 lines, functions ≤ 60 lines, nesting depth ≤ 3, and
  ≤ 3 parameters for new functions. Blank lines and comments don't count.
- Enforced by ruff: cyclomatic complexity ≤ 10 (`C901`), ≤ 12 branches, ≤ 5 arguments. The
  argument limit exists for Django/DRF/invoke signatures you can't change. For new functions over
  3 parameters, prefer passing a dataclass or `TypedDict`. Existing functions over 3 parameters
  (e.g. `rewrite_env`) aren't changed just for this.
- Approaching a limit means a function or module does too much. Split it by responsibility, not
  by line count. Existing large files aren't split for their own sake; when you change one
  substantially, split along responsibilities.

## Modularity

- One responsibility per module, named after what it holds (`locales.py`, `importer.py`).
- Only the public API has no leading underscore; module-internal helpers are `_private`.
- Dependencies point one way: views → serializers/services → models → pure helpers. No import
  cycles, and app code never imports from `tests/`.

## Naming

- Use declarative names that say what something is or does: `get_requested_locale`,
  `default_dev_server_port`. No bare generic names (`data`, `util`, `helper`, `manager`, `tmp`)
  in your own code; names a framework dictates stay.
- Booleans read as questions: `is_`, `has_`, `can_`, `should_`.
- Constants in `UPPER_CASE`, with the unit in the name when there is one: `TIMEOUT_SECONDS`.
- Prefer `enum.StrEnum` or Django `TextChoices` over boolean flags or bare string constants where
  an enum fits. Parse untrusted strings into the enum at the boundary.

## Pythonic code

Ruff (`C4`, `SIM`, `UP`, `RET`, `PERF`, `B`, `PIE`, `PTH`, `FURB`) enforces many of these.

- Comprehensions and generator expressions over `append` loops; `any`/`all` over flag loops.
- `enumerate` and `zip` over index counters; unpacking over indexing.
- f-strings, not `%` or `format`. `pathlib.Path`, not `os.path`.
- Context managers for files, locks and transactions (`transaction.atomic()`).
- `raise NewError(...) from err`, or `from None` to hide the cause deliberately
  (`raise Http404 from None` in `image_auth/views.py`).
- Early returns; no `else` after `return`. No nested conditional expressions.
- No mutable default arguments. `dict.get(key, default)` over `if key in d` lookups.

## Comments

- Only comment when a name can't explain it: the _why_, an external constraint or a library
  quirk. Never restate the code.
- Rename or extract a function instead of commenting what a block does.
- Docstrings say what a function returns or guarantees, in one line where possible.

## Types

- Production code is fully annotated (ruff `ANN`). Tests and migrations are exempt from `ANN`,
  and migrations are also exempt from the Pythonic and complexity rules.
- mypy with `django-stubs` and `djangorestframework-stubs` checks all of `src/` and `tasks.py`.
  Untyped libraries (Wagtail, social-auth, modelcluster, storages, invoke) are handled per module
  with `ignore_missing_imports` in `pyproject.toml`.
- Modern syntax: `X | None`, builtin generics (`list[str]`), `collections.abc` for abstract types.
- `*args: Any, **kwargs: Any` for pass-through signatures is fine. Otherwise prefer precise types
  over `Any`: `oidc_auth/pipeline.py` annotates the social-auth `BaseAuth` and `BaseStrategy`.
- Narrow `object` or unvalidated data at the boundary instead of casting.

## Testing

- New features and behaviour changes get tests in `<app>/tests/test_*.py`, using Django's test
  runner (not pytest), mirroring the module under test. Split large test modules by scenario.
- Tests are behaviour-focused: assert on results, not on internals.

## Before finishing

Run `uv run invoke format`, `uv run invoke lint` and `uv run invoke test` (the stack runs in watch
mode, see `CLAUDE.md`). Re-read the diff and remove dead code, debug prints, unused imports and
anything the task didn't need.

## Workflow

- Implement code on feature branches, never directly on `main`.
- Fix existing findings in the same change that exposes them; keep format-only changes in their
  own commit.

## Committing changes

- Start commit messages with a capital-letter verb in imperative mood, without a prefix:
  `Move API errors into their own module`.
- Keep commit messages short.
- Only use a body for complex commits.
- Prefer small, granular commits over a single commit with a body explaining multiple changes.
