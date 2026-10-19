"""Runtime registry of the social sign-in providers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlunsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from social_django.models import UserSocialAuth

from oidc_auth.config import AUTH0, LOCAL, ZITADEL

ZITADEL_ROLES_CLAIM = "urn:zitadel:iam:org:project:roles"


def read_claim(backend: Any, response: dict[str, Any], claim: str) -> Any:
    """Read a claim, preferring the validated ID token over the userinfo response."""
    id_token = getattr(backend, "id_token", None)
    if isinstance(id_token, dict) and claim in id_token:
        return id_token[claim]
    return response.get(claim)


def read_auth0_roles(backend: Any, response: dict[str, Any]) -> set[str]:
    """Auth0 roles: a list under AUTH0_ROLES_CLAIM. Malformed means no roles."""
    claim = settings.AUTH0_ROLES_CLAIM
    if not claim:
        raise ImproperlyConfigured(
            "AUTH0_ROLES_CLAIM must be set to sync Auth0 roles to Wagtail groups."
        )
    raw = read_claim(backend, response, claim)
    if not isinstance(raw, list):
        return set()
    return {role for role in raw if isinstance(role, str)}


def read_zitadel_roles(backend: Any, response: dict[str, Any]) -> set[str]:
    """Zitadel roles: the keys of an object claim. Anything else means no roles."""
    raw = read_claim(backend, response, ZITADEL_ROLES_CLAIM)
    if not isinstance(raw, dict):
        return set()
    return {role for role in raw if isinstance(role, str)}


def auth0_logout_url(
    request: HttpRequest, social: UserSocialAuth, return_to: str
) -> str:
    params = {
        "client_id": settings.SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY,
        "returnTo": return_to,
    }
    return urlunsplit(
        (
            "https",
            settings.SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN,
            "/v2/logout",
            urlencode(params),
            "",
        )
    )


def zitadel_logout_url(
    request: HttpRequest, social: UserSocialAuth, return_to: str
) -> str:
    params = {
        "client_id": settings.SOCIAL_AUTH_ZITADEL_KEY,
        "post_logout_redirect_uri": return_to,
    }
    id_token = (social.extra_data or {}).get("id_token")
    if id_token:
        params["id_token_hint"] = id_token
    return urlunsplit(
        (
            "https",
            settings.SOCIAL_AUTH_ZITADEL_DOMAIN,
            "/oidc/v1/end_session",
            urlencode(params),
            "",
        )
    )


@dataclass(frozen=True)
class Provider:
    id: str
    backend_name: str
    label: str
    read_roles: Callable[[Any, dict[str, Any]], set[str]]
    logout_url: Callable[[HttpRequest, UserSocialAuth, str], str]


PROVIDERS: dict[str, Provider] = {
    AUTH0: Provider(
        AUTH0, "auth0_openidconnect", "Auth0", read_auth0_roles, auth0_logout_url
    ),
    ZITADEL: Provider(
        ZITADEL, "zitadel", "Zitadel", read_zitadel_roles, zitadel_logout_url
    ),
}


def enabled_social_providers() -> list[Provider]:
    """Enabled social providers in AUTH_PROVIDERS order (local is skipped)."""
    return [PROVIDERS[name] for name in settings.AUTH_PROVIDERS if name != LOCAL]


def provider_for_backend(backend_name: str) -> Provider | None:
    for provider in PROVIDERS.values():
        if provider.backend_name == backend_name:
            return provider
    return None
