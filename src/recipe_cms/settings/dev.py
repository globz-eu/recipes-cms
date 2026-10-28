import os

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

# The frontend dev server (Vite) proxies to this backend from another port.
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173"]

# Distinct cookie names let several dev stacks share one browser (cookies are
# scoped per host, not per port).
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "sessionid")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "csrftoken")
