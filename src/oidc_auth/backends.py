from django.contrib.auth.backends import ModelBackend
from social_core.backends.open_id_connect import OpenIdConnectAuth


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
        "offline_access",
    ]

    def oidc_endpoint(self) -> str:
        return f"https://{self.setting('DOMAIN')}"
