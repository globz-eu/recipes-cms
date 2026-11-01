from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ImproperlyConfigured
from social_core.backends.open_id_connect import OpenIdConnectAuth

ZITADEL_ORG_SCOPE_PREFIX = "urn:zitadel:iam:org:id:"


class PermissionsOnlyBackend(ModelBackend):
    """Never authenticates; keeps group/user permissions working when password
    login is disabled."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        return None


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
        """The configured scopes plus the org scope of ZITADEL_ROLE_ORG_ID.

        The org scope makes Zitadel apply that org's login settings and branding
        and admit only its users, so it is added even with IGNORE_DEFAULT_SCOPE.
        """
        org_id = settings.ZITADEL_ROLE_ORG_ID
        if not org_id:
            raise ImproperlyConfigured(
                "ZITADEL_ROLE_ORG_ID must be set to scope Zitadel logins to its org."
            )
        org_scope = f"{ZITADEL_ORG_SCOPE_PREFIX}{org_id}"
        return [*(s for s in super().get_scope() if s != org_scope), org_scope]
