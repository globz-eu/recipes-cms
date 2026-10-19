"""Pure settings helpers for the AUTH_PROVIDERS switch.

Imported by the settings module, so nothing here may import Django models
or anything beyond ``ImproperlyConfigured``.
"""

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ImproperlyConfigured

LOCAL = "local"
AUTH0 = "auth0"
ZITADEL = "zitadel"

SOCIAL_BACKENDS: dict[str, str] = {
    AUTH0: "social_core.backends.auth0_openidconnect.Auth0OpenIdConnectAuth",
    ZITADEL: "oidc_auth.backends.ZitadelOpenIdConnect",
}

REQUIRED_SETTINGS: dict[str, tuple[str, ...]] = {
    LOCAL: (),
    AUTH0: (
        "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN",
        "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY",
        "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET",
        "AUTH0_ROLES_CLAIM",
    ),
    ZITADEL: (
        "SOCIAL_AUTH_ZITADEL_DOMAIN",
        "SOCIAL_AUTH_ZITADEL_KEY",
        "SOCIAL_AUTH_ZITADEL_SECRET",
    ),
}

MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
PERMISSIONS_ONLY_BACKEND = "oidc_auth.backends.PermissionsOnlyBackend"


def parse_auth_providers(value: str) -> list[str]:
    """Parse the comma-separated AUTH_PROVIDERS value, keeping order."""
    allowed = ", ".join(REQUIRED_SETTINGS)
    names = [part.strip().lower() for part in value.split(",")]
    if not any(names):
        raise ImproperlyConfigured(
            f"AUTH_PROVIDERS must name at least one provider ({allowed})."
        )
    providers: list[str] = []
    for name in names:
        if name not in REQUIRED_SETTINGS:
            raise ImproperlyConfigured(
                f"Unknown AUTH_PROVIDERS entry {name!r}; allowed: {allowed}."
            )
        if name not in providers:
            providers.append(name)
    return providers


def authentication_backends(providers: list[str]) -> list[str]:
    """Social backends in provider order, then the password or permissions backend."""
    backends = [SOCIAL_BACKENDS[name] for name in providers if name in SOCIAL_BACKENDS]
    backends.append(MODEL_BACKEND if LOCAL in providers else PERMISSIONS_ONLY_BACKEND)
    return backends


def check_provider_settings(providers: list[str], values: Mapping[str, Any]) -> None:
    """Raise ImproperlyConfigured naming every setting an enabled provider lacks."""
    problems = []
    for provider in providers:
        missing = [n for n in REQUIRED_SETTINGS[provider] if not values.get(n)]
        if missing:
            problems.append(f"{provider}: {', '.join(missing)}")
    if problems:
        raise ImproperlyConfigured(
            "AUTH_PROVIDERS enables providers whose settings are missing or "
            "empty: " + "; ".join(problems)
        )
