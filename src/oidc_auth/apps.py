from django.apps import AppConfig


class OidcAuthConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "oidc_auth"
