import sys
from pathlib import Path

from invoke.exceptions import Exit
from invoke.tasks import task

sys.path.insert(0, str(Path(__file__).parent / "src"))

from home.worktree_env import (  # noqa: E402
    check_ports,
    default_postgres_port,
    default_project_name,
    rewrite_env,
    sanitize_name,
)


@task(
    help={"part": "Part of the version to bump: major, minor, patch (default: patch)"}
)
def bump(c, part="patch"):
    """Bump version using uv version and create a git tag."""
    result = c.run("git status --short", hide=True)
    if result.stdout != "":
        print("Working directory is not clean. Please commit or stash changes first.")
        return
    c.run(f"uv version --bump {part}")
    c.run("uv lock")
    c.run("git add pyproject.toml uv.lock")
    new_version = c.run("uv version --short", hide=True).stdout.strip()
    c.run(f'git commit -m "{new_version}"')
    c.run(f"git tag -a v{new_version} -m '{new_version}'")


@task
def format(c):
    """Format code using ruff."""
    c.run("uv run ruff check --fix src")
    c.run("uv run ruff format src")


@task(
    help={
        "label": "Test label(s) to run (default: all tests).",
        "verbosity": "Verbosity level: 0, 1, or 2 (default: 1).",
    }
)
def test(c, label="", verbosity=1):
    """Run the Django test suite inside the wagtail Docker Compose service."""
    c.run(
        f"docker compose exec wagtail uv run manage.py test {label} --verbosity={verbosity}",
        pty=sys.stdout.isatty(),
    )


@task(help={"build": "Build images before running the development server."})
def dev(c, build=False):
    """Run the development server with docker compose."""
    c.run(
        f"docker compose up {'--build' if build else ''} --watch",
        pty=sys.stdout.isatty(),
    )


@task(help={"volumes": "Also remove volumes (resets database, static files, media)."})
def down(c, volumes=False):
    """Stop and remove this directory's dev stack (stop `invoke dev` first)."""
    c.run(f"docker compose down {'-v' if volumes else ''}", pty=sys.stdout.isatty())


def _main_worktree(c):
    out = c.run("git worktree list --porcelain", hide=True).stdout
    return Path(out.splitlines()[0].removeprefix("worktree ")).resolve()


@task(
    help={
        "port": "Host port for nginx (required, e.g. 8081).",
        "db_port": "Host port for postgres (default: port - 8080 + 5432).",
        "name": "Compose project name (default: recipes-cms-<directory name>).",
        "source": "Source .env (default: the main worktree's).",
        "force": (
            "Overwrite an existing .env (rebuilt from the source; edits are lost)."
        ),
    }
)
def worktree_env(c, port=None, db_port=None, name=None, source=None, force=False):
    """Write this worktree's .env with its own project name, ports and cookies."""
    # invoke does not chdir to this file; tasks.py sits at the worktree root.
    here = Path(__file__).resolve().parent
    main = _main_worktree(c)
    if here == main:
        raise Exit("This is the main worktree; its .env is the source. Aborting.")
    if port is None:
        raise Exit("--port is required (e.g. --port 8081).")
    try:
        port = int(port)
        db_port = int(db_port) if db_port is not None else default_postgres_port(port)
        check_ports(port, db_port)
        name = sanitize_name(name) if name else default_project_name(here.name)
    except ValueError as error:
        raise Exit(str(error)) from error
    source = Path(source) if source else main / ".env"
    target = here / ".env"
    if target.exists() and not force:
        raise Exit(f"{target} exists; use --force to overwrite it.")
    if not source.is_file():
        raise Exit(f"Source {source} not found.")
    target.write_text(rewrite_env(source.read_text(), name, port, db_port))
    target.chmod(source.stat().st_mode & 0o777)
    print(f"Wrote {target} (project {name}, nginx :{port}, postgres :{db_port}).")
