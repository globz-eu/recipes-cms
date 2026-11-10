from typing import Any

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from social_core.backends.auth0_openidconnect import Auth0OpenIdConnectAuth
from social_core.backends.open_id_connect import OpenIdConnectAuth

ZITADEL_ORG_SCOPE_PREFIX = "urn:zitadel:iam:org:id:"
ZITADEL_RESOURCE_OWNER_SCOPE = "urn:zitadel:iam:user:resourceowner"


class PermissionsOnlyBackend(ModelBackend):
    """Never authenticates; keeps group/user permissions working when password
    login is disabled."""

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        return None


class Auth0OpenIdConnect(Auth0OpenIdConnectAuth):
    """Auth0 sign-in whose discovery URL has no double slash.

    Upstream ``oidc_endpoint`` ends in a slash and ``oidc_config`` appends
    ``/.well-known/openid-configuration``; Auth0 answers the resulting ``//``
    URL with 404. The backend name, and so every URL, stays upstream's.
    """

    def oidc_endpoint(self) -> str:
        return f"https://{self.setting('DOMAIN')}"


class ZitadelOpenIdConnect(OpenIdConnectAuth):
    """Zitadel sign-in. SOCIAL_AUTH_ZITADEL_DOMAIN is the bare instance host."""

    name = "zitadel"
    DEFAULT_SCOPE = [
        "openid",
        "profile",
        "email",
        "urn:zitadel:iam:org:project:roles",
    ]

    def oidc_endpoint(self) -> str:
        return f"https://{self.setting('DOMAIN')}"

    def get_scope(self) -> list[str]:
        """The configured scopes plus the org and resource owner scopes.

        The org scope of ZITADEL_ROLE_ORG_ID makes Zitadel apply that org's login
        settings and branding and admit only its users. The resource owner scope
        makes Zitadel send the user's org id claim, without which
        ``enforce_zitadel_org`` refuses the login. Both are added once, even with
        IGNORE_DEFAULT_SCOPE.
        """
        org_id = settings.ZITADEL_ROLE_ORG_ID
        if not org_id:
            raise ImproperlyConfigured(
                "ZITADEL_ROLE_ORG_ID must be set to scope Zitadel logins to its org."
            )
        org_scope = f"{ZITADEL_ORG_SCOPE_PREFIX}{org_id}"
        required = [org_scope, ZITADEL_RESOURCE_OWNER_SCOPE]
        return [*(s for s in super().get_scope() if s not in required), *required]
