from django.apps import AppConfig
from wagtail.users.apps import WagtailUsersAppConfig


class OidcAuthConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "oidc_auth"


class CustomUsersAppConfig(WagtailUsersAppConfig):
    user_viewset = "oidc_auth.viewsets.OwnedEmailUserViewSet"
