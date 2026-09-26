import os

from corsheaders.defaults import default_headers, default_methods

from .base import *  # noqa: F403

DEBUG = False


def env_list(name: str) -> list[str]:
    """Read a comma-separated environment variable into a list, skipping blanks."""
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

# Origins allowed to submit unsafe (POST, PUT, ...) requests, e.g. the frontend
# served from the static CDN host.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Cross-origin API access for the frontend served from the static CDN host.
# Credentials are required so the session cookie is sent along.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers,)
CORS_ALLOW_METHODS = (*default_methods,)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Hosts (besides the current one) that login/logout may redirect back to.
SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS = env_list("SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS")
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/6.0/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"]["BACKEND"] = (  # noqa: F405
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)

# When a static bucket is configured, static files are collected to S3 and
# served from a CDN domain instead of the local filesystem.
STATIC_BUCKET_NAME = os.getenv("STATIC_BUCKET_NAME")
STATIC_CUSTOM_DOMAIN = os.getenv("STATIC_CUSTOM_DOMAIN")
if STATIC_BUCKET_NAME:
    STORAGES["staticfiles"] = {  # noqa: F405
        "BACKEND": "storages.backends.s3.S3ManifestStaticStorage",
        "OPTIONS": {
            "bucket_name": STATIC_BUCKET_NAME,
            "location": "static",
            "custom_domain": STATIC_CUSTOM_DOMAIN,
            "querystring_auth": False,
            # Served publicly by the CDN (bucket website endpoint).
            "default_acl": "public-read",
            "file_overwrite": True,
        },
    }
    if STATIC_CUSTOM_DOMAIN:
        STATIC_URL = f"https://{STATIC_CUSTOM_DOMAIN}/static/"

SOCIAL_AUTH_JSONFIELD_ENABLED = True

BASE_PATH = os.getenv("BASE_PATH", "/")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
