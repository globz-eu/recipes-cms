from invoke.tasks import task


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


@task(help={"build": "Build images before running the development server."})
def dev(c, build=False):
    """Run the development server with docker compose."""
    c.run(f"docker compose up {'--build' if build else ''} --watch", pty=True)
