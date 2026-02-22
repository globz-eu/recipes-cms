from django.apps import AppConfig


class Auth0AuthConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "auth0_auth"
