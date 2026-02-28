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
