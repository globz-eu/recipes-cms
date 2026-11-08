"""Settings for the test suite on the host: SQLite and in-memory storage.

Needs no .env, Postgres or S3. Values already in the environment win, so the
suite can still run against Postgres (`invoke test --postgres`).
"""

import os

# Set before base is imported: it reads these at import time.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
# Auth0 stays enabled (the default providers) with dummy credentials, as the
# sign-in tests exercise it; nothing here contacts Auth0.
for _name, _value in {
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN": "example.auth0.com",
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY": "test-client-id",
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET": "test-client-secret",
    "AUTH0_ROLES_CLAIM": "https://recipes.example/roles",
}.items():
    os.environ.setdefault(_name, _value)

from .dev import *  # noqa: E402, F403 -- settings extend dev via star import

if not os.getenv("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

STORAGES = {
    **STORAGES,  # noqa: F405 -- from the star import
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
