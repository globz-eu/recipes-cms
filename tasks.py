import sys
from pathlib import Path
from typing import Any

from invoke.context import Context
from invoke.exceptions import Exit
from invoke.runners import Result
from invoke.tasks import task

sys.path.insert(0, str(Path(__file__).parent / "src"))

from home.worktree_env import (  # noqa: E402 -- src/ must be on sys.path first
    check_ports,
    default_dev_server_port,
    default_postgres_port,
    default_project_name,
    rewrite_env,
    sanitize_name,
)


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


@task(
    help={
        "label": "Test label(s) to run (default: all tests).",
        "verbosity": "Verbosity level: 0, 1, or 2 (default: 1).",
    }
)
def test(c: Context, label: str = "", verbosity: int = 1) -> None:
    """Run the Django test suite on the host with SQLite (settings.test)."""
    with c.cd("src"):
        c.run(
            f"uv run manage.py test {label} --verbosity={verbosity}",
            pty=sys.stdout.isatty(),
        )


@task(help={"build": "Build images before running the development server."})
def dev(c: Context, build: bool = False) -> None:
    """Run the development server with docker compose."""
    c.run(
        f"docker compose up {'--build' if build else ''} --watch",
        pty=sys.stdout.isatty(),
    )


@task(help={"volumes": "Also remove volumes (resets database, static files, media)."})
def down(c: Context, volumes: bool = False) -> None:
    """Stop and remove this directory's dev stack (stop `invoke dev` first)."""
    c.run(f"docker compose down {'-v' if volumes else ''}", pty=sys.stdout.isatty())


def _main_worktree(c: Context) -> Path:
    out = _run(c, "git worktree list --porcelain", hide=True).stdout
    return Path(out.splitlines()[0].removeprefix("worktree ")).resolve()


@task(
    help={
        "port": "Host port for nginx (required, e.g. 8081).",
        "db_port": "Host port for postgres (default: port - 8080 + 5432).",
        "dev_server_port": (
            "Frontend dev server port trusted besides 5173"
            " (default: port - 8080 + 5173)."
        ),
        "name": "Compose project name (default: recipes-cms-<directory name>).",
        "source": "Source .env (default: the main worktree's).",
        "force": (
            "Overwrite an existing .env (rebuilt from the source; edits are lost)."
        ),
    }
)
def worktree_env(  # noqa: PLR0913 -- parameters are invoke CLI flags
    c: Context,
    port: str | None = None,
    db_port: str | None = None,
    dev_server_port: str | None = None,
    name: str | None = None,
    source: str | None = None,
    force: bool = False,
) -> None:
    """Write this worktree's .env with its own project name, ports and cookies."""
    # invoke does not chdir to this file; tasks.py sits at the worktree root.
    here = Path(__file__).resolve().parent
    main = _main_worktree(c)
    if here == main:
        raise Exit("This is the main worktree; its .env is the source. Aborting.")
    if port is None:
        raise Exit("--port is required (e.g. --port 8081).")
    try:
        nginx_port = int(port)
        derived = set()
        postgres_port = (
            int(db_port) if db_port is not None else default_postgres_port(nginx_port)
        )
        if db_port is None:
            derived.add("--db-port")
        frontend_port = (
            int(dev_server_port)
            if dev_server_port is not None
            else default_dev_server_port(nginx_port)
        )
        if dev_server_port is None:
            derived.add("--dev-server-port")
        check_ports(nginx_port, postgres_port, frontend_port, derived)
        project_name = sanitize_name(name) if name else default_project_name(here.name)
    except ValueError as error:
        raise Exit(str(error)) from error
    source_path = Path(source) if source else main / ".env"
    target = here / ".env"
    if target.exists() and not force:
        raise Exit(f"{target} exists; use --force to overwrite it.")
    if not source_path.is_file():
        raise Exit(f"Source {source_path} not found.")
    target.write_text(
        rewrite_env(
            source_path.read_text(),
            project_name,
            nginx_port,
            postgres_port,
            frontend_port,
        )
    )
    target.chmod(source_path.stat().st_mode & 0o777)
    print(
        f"Wrote {target} (project {project_name}, nginx :{nginx_port},"
        f" postgres :{postgres_port}, dev server :{frontend_port})."
    )
