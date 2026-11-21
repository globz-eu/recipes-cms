# Compact recipes-cms CLAUDE.md

## Goal
- Cut `CLAUDE.md` from ~12 KB to ~6-7 KB without losing working knowledge.
- Only `CLAUDE.md` changes; drop rather than move.

## What to cut / keep
- Commands: cut stack/worktree/cleanup prose, already in `~/.claude/architectures/recipes.md`.
- Commands: keep `invoke dev|down|test|format|lint|bump` list (all exist in `tasks.py`).
- Commands: keep Postgres-verification rule and "use `invoke dev`, not `docker compose up`".
- Commands: keep `.env` setup in one line; `RECIPES_INFRA_DIR` one line.
- PR #22 note: delete; PR merged 2026-11-08, `dev-stack.sh` is on recipes-infrastructure `main` (no tags yet).
- `oidc_auth`: cut to invariants: one email/one provider, `LoginRefused` codes, fail-closed Zitadel org check.
- `oidc_auth`: point to `config.py`, `pipeline.py`, `providers.py`, `tests/login_harness.py` for the rest.
- `home`, `recipes`, `image_auth`, nginx: one or two bullets each.
- Multilingual model and bulk import semantics: keep (non-obvious), tighten wording.
- Deployment notes: drop what the architecture file covers; keep `HealthCheckMiddleware` and Dockerfile `/opt/venv`.
- Conventions: drop commit rules (duplicated in `.claude/rules/code-quality.md`); keep rule-file pointers and lint requirement.

## Acceptance criteria
1. `CLAUDE.md` is at most 7 KB (`wc -c`), at least 40% smaller.
2. Still imports `@~/.claude/architectures/recipes.md`.
3. Every path, task name and setting named in it exists (checked by grep).
4. The PR #22 note is gone.
5. No content duplicated from the architecture file or rules files.
6. `uv run invoke lint` passes unchanged; no other file edited.

## Implementation steps
- Verify kept claims against `tasks.py`, `settings/`, `oidc_auth/`, `home/`, `recipes/`.
- Rewrite `CLAUDE.md` in one commit, terse bullets.

## Open questions
- Should the full `oidc_auth` pipeline detail go to README or be dropped? Plan says drop.
