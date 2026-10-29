import os
from urllib.parse import urlsplit

from .base import *  # noqa: F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
SERVE_STATIC = False

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

BASE_PATH = os.getenv("BASE_PATH", "/")

USE_X_FORWARDED_PORT = True

DEV_PASSWORD_LOGIN = True

# Frontend dev servers (Vite) proxying to this backend. The proxy keeps the
# browser's Origin (http://localhost:<vite port>) while nginx forwards the nginx
# host, so Django sees a cross-origin request: trust each dev server origin.
# One entry per dev server, comma-separated (`invoke worktree-env` sets it).
CSRF_TRUSTED_ORIGINS = env_list(  # noqa: F405
    "DEV_FRONTEND_ORIGINS", default=["http://localhost:5173"]
)

# Login/logout may redirect back to those dev servers (`next`); the hosts are
# compared with their port.
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = [
    urlsplit(origin).netloc for origin in CSRF_TRUSTED_ORIGINS
]

# Distinct cookie names let several dev stacks share one browser (cookies are
# scoped per host, not per port).
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME") or "sessionid"
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME") or "csrftoken"
