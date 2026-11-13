import os
import shlex
import sys
from pathlib import Path
from typing import Any

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.runners import Result
from invoke.tasks import task

HERE = Path(__file__).resolve().parent
COMPOSE_DEV = shlex.quote(str(HERE / "compose.dev.yml"))


def _run(c: Context, command: str, **kwargs: Any) -> Result:
    """`c.run` that returns the Result; it is only None for `disown=True`."""
    result = c.run(command, **kwargs)
    if result is None:
        raise RuntimeError(f"invoke returned no result for: {command}")
    return result


@task(
    help={"part": "Part of the version to bump: major, minor, patch (default: patch)"}
)
def bump(c: Context, part: str = "patch") -> None:
    """Bump version using uv version and create a git tag."""
    result = _run(c, "git status --short", hide=True)
    if result.stdout != "":
        print("Working directory is not clean. Please commit or stash changes first.")
        return
    c.run(f"uv version --bump {part}")
    c.run("uv lock")
    c.run("git add pyproject.toml uv.lock")
    new_version = _run(c, "uv version --short", hide=True).stdout.strip()
    c.run(f'git commit -m "{new_version}"')
    c.run(f"git tag -a v{new_version} -m '{new_version}'")


@task
def format(c: Context) -> None:
    """Format code using ruff."""
    c.run("uv run ruff check --fix src tasks.py")
    c.run("uv run ruff format src tasks.py")


@task
def lint(c: Context) -> None:
    """Check code with ruff (lint and format) and mypy; changes nothing."""
    # The mypy django plugin imports the settings on the host; one provider avoids
    # needing the social-login variables.
    env = {"AUTH_PROVIDERS": "local"}
    results = [
        _run(c, "uv run ruff check src tasks.py", warn=True, env=env),
        _run(c, "uv run ruff format --check src tasks.py", warn=True, env=env),
        _run(c, "uv run mypy", warn=True, env=env),
    ]
    if any(result.failed for result in results):
        raise Exit("Lint failed.")


def _main_worktree(c: Context) -> Path:
    out = _run(c, "git worktree list --porcelain", hide=True).stdout
    return Path(out.splitlines()[0].removeprefix("worktree ")).resolve()


def _env_file_value(key: str) -> str | None:
    """Last `KEY=value` in this worktree's .env, if any (invoke does not load it)."""
    try:
        lines = (HERE / ".env").read_text().splitlines()
    except OSError:
        return None
    value = None
    for line in lines:
        name, sep, raw = line.strip().removeprefix("export ").partition("=")
        if sep and name.strip() == key:
            value = raw.strip().strip("\"'")
    return value


def _dev_stack_script(c: Context) -> Path:
    """The recipes-infrastructure dev-stack.sh; RECIPES_INFRA_DIR overrides the sibling."""
    configured = os.environ.get("RECIPES_INFRA_DIR") or _env_file_value(
        "RECIPES_INFRA_DIR"
    )
    infra = (
        Path(configured).expanduser()
        if configured
        else _main_worktree(c).parent / "recipes-infrastructure"
    )
    script = infra / "scripts" / "dev-stack.sh"
    if not script.is_file():
        raise Exit(
            f"{script} not found. Clone recipes-infrastructure next to this"
            " repository or set RECIPES_INFRA_DIR to its checkout; see its README,"
            ' section "Local dev environment".'
        )
    return script


def _dev_stack(c: Context, arguments: str, **kwargs: Any) -> Result:
    """Run dev-stack.sh from this worktree, the directory that identifies the stack."""
    script = _dev_stack_script(c)
    with c.cd(str(HERE)):
        return _run(c, f"sh {shlex.quote(str(script))} {arguments}", **kwargs)


@task(
    help={
        "label": "Test label(s) to run (default: all tests).",
        "verbosity": "Verbosity level: 0, 1, or 2 (default: 1).",
        "postgres": "Run in the dev stack's container against Postgres, not SQLite.",
    }
)
def test(
    c: Context, label: str = "", verbosity: int = 1, postgres: bool = False
) -> None:
    """Run the Django test suite: on the host with SQLite, or --postgres in Docker."""
    if postgres:
        # run --build keeps the image in step with src/. The image bakes in dev
        # settings (S3); test settings keep Postgres since POSTGRES_HOST is set.
        _dev_stack(
            c,
            f"compose -f {COMPOSE_DEV} run --build --rm"
            " -e DJANGO_SETTINGS_MODULE=recipe_cms.settings.test wagtail"
            f" python manage.py test {label} --verbosity={verbosity}",
            pty=sys.stdout.isatty(),
        )
        return
    with c.cd("src"):
        c.run(
            f"uv run manage.py test {label} --verbosity={verbosity}",
            pty=sys.stdout.isatty(),
        )


@task(help={"build": "Build images before running the development server."})
def dev(c: Context, build: bool = False) -> None:
    """Run the dev stack (recipes-infrastructure base + compose.dev.yml) with watch."""
    _dev_stack(
        c,
        f"up --watch {'--build' if build else ''} --skip-lookup CMS_VERSION"
        f" -f {COMPOSE_DEV}",
        pty=sys.stdout.isatty(),
    )


@task(help={"volumes": "Also remove volumes (resets database, static files, media)."})
def down(c: Context, volumes: bool = False) -> None:
    """Stop and remove this directory's dev stack (stop `invoke dev` first)."""
    _dev_stack(c, f"down {'-v' if volumes else ''}", pty=sys.stdout.isatty())
