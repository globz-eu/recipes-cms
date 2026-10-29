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
    "DEV_FRONTEND_ORIGINS",
)
HEADER = "# Local dev stack of this worktree (written by `invoke worktree-env`)"
MIN_PORT = 1024
MAX_PORT = 65535
DEFAULT_NGINX_PORT = 8080
DEFAULT_POSTGRES_PORT = 5432
# Vite's default port; the frontend dev server of the main stack.
DEFAULT_DEV_SERVER_PORT = 5173


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


def default_dev_server_port(port):
    """Pair a frontend dev server port with the nginx port (8081 -> 5174)."""
    return port - DEFAULT_NGINX_PORT + DEFAULT_DEV_SERVER_PORT


def dev_frontend_origins(dev_server_port):
    """Dev server origins to trust: 5173 (any stack) plus this stack's port."""
    ports = dict.fromkeys((DEFAULT_DEV_SERVER_PORT, dev_server_port))
    return ",".join(f"http://localhost:{p}" for p in ports)


def check_ports(port, db_port, dev_server_port=None, derived=()):
    """Raise ValueError unless the ports are usable for an extra stack.

    `dev_server_port` (the frontend dev server) may be 5173: it is a valid
    choice for a single dev server, which then targets this stack. It must not
    be a host port of this stack or of the main stack. `derived` names the
    options (`--db-port`, `--dev-server-port`) whose value was derived from
    `port`; an
    out-of-range error for them suggests passing the option explicitly.
    """
    checks = [
        ("--port", port, DEFAULT_NGINX_PORT),
        ("--db-port", db_port, DEFAULT_POSTGRES_PORT),
    ]
    if dev_server_port is not None:
        checks.append(("--dev-server-port", dev_server_port, None))
    for label, value, main in checks:
        if not MIN_PORT <= value <= MAX_PORT:
            raise ValueError(
                f"{label} {value} is outside {MIN_PORT}-{MAX_PORT}"
                + (f" (pass {label} explicitly)" if label in derived else "")
            )
        if value == main:
            raise ValueError(f"{label} {value} is used by the main stack")
    if dev_server_port in (DEFAULT_NGINX_PORT, DEFAULT_POSTGRES_PORT):
        raise ValueError(
            f"--dev-server-port {dev_server_port} is used by the main stack"
        )
    if dev_server_port in (port, db_port):
        raise ValueError(
            f"--dev-server-port {dev_server_port} is a host port of this stack"
        )


def _key(line):
    match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
    return match.group(1) if match else None


def rewrite_env(text, name, port, db_port, dev_server_port=None):
    """Return `text` with the stack-specific variables set for a worktree.

    Existing definitions of the managed variables are replaced, the derived URLs
    are dropped, everything else is kept as is. `dev_server_port` defaults to
    the port paired with `port` (`default_dev_server_port`).
    """
    name = sanitize_name(name)
    if dev_server_port is None:
        dev_server_port = default_dev_server_port(port)
    dropped = set(MANAGED_KEYS) | set(DERIVED_KEYS)
    kept = [
        line
        for line in text.splitlines()
        if _key(line) not in dropped and line != HEADER
    ]
    while kept and not kept[-1].strip():
        kept.pop()
    block = [
        HEADER,
        f"COMPOSE_PROJECT_NAME={name}",
        f"NGINX_HOST_PORT={port}",
        f"POSTGRES_HOST_PORT={db_port}",
        f"SESSION_COOKIE_NAME={name}_sessionid",
        f"CSRF_COOKIE_NAME={name}_csrftoken",
        f"DEV_FRONTEND_ORIGINS={dev_frontend_origins(dev_server_port)}",
    ]
    return "\n".join([*kept, "", *block]) + "\n"
