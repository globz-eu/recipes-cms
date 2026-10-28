"""Rewrite a dev `.env` for an extra git worktree (used by `invoke worktree-env`).

Kept free of invoke and git so it can be tested on its own.
"""

import re

# Derived again from NGINX_HOST_PORT once removed (see compose.yml).
DERIVED_KEYS = ("S3_CUSTOM_DOMAIN", "WAGTAILADMIN_BASE_URL")
MANAGED_KEYS = (
    "COMPOSE_PROJECT_NAME",
    "NGINX_HOST_PORT",
    "POSTGRES_HOST_PORT",
    "SESSION_COOKIE_NAME",
    "CSRF_COOKIE_NAME",
)
DEFAULT_NGINX_PORT = 8080
DEFAULT_POSTGRES_PORT = 5432


def default_project_name(directory_name):
    """Compose project name from a worktree directory name."""
    return sanitize_name(f"recipes-cms-{directory_name}")


def sanitize_name(name):
    """Lowercase, keep [a-z0-9_-], and start with a letter or digit."""
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", name.lower()).strip("-_")
    if not cleaned:
        raise ValueError(f"Cannot derive a project name from {name!r}")
    return cleaned


def default_postgres_port(port):
    """Keep the offset between the nginx and postgres defaults (8081 -> 5433)."""
    return port - DEFAULT_NGINX_PORT + DEFAULT_POSTGRES_PORT


def _key(line):
    match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
    return match.group(1) if match else None


def rewrite_env(text, name, port, db_port):
    """Return `text` with the stack-specific variables set for a worktree.

    Existing definitions of the managed variables are replaced, the derived URLs
    are dropped, everything else is kept as is.
    """
    name = sanitize_name(name)
    dropped = set(MANAGED_KEYS) | set(DERIVED_KEYS)
    kept = [line for line in text.splitlines() if _key(line) not in dropped]
    while kept and not kept[-1].strip():
        kept.pop()
    block = [
        "# Local dev stack of this worktree (written by `invoke worktree-env`)",
        f"COMPOSE_PROJECT_NAME={name}",
        f"NGINX_HOST_PORT={port}",
        f"POSTGRES_HOST_PORT={db_port}",
        f"SESSION_COOKIE_NAME={name}_sessionid",
        f"CSRF_COOKIE_NAME={name}_csrftoken",
    ]
    return "\n".join([*kept, "", *block]) + "\n"
