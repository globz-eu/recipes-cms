from django.conf import settings
from django.http import HttpRequest

from oidc_auth.config import LOCAL
from oidc_auth.providers import enabled_social_providers


def auth_providers(request: HttpRequest) -> dict:
    """Expose the enabled sign-in providers to the login page templates."""
    return {
        "social_auth_providers": [
            {"label": p.label, "backend_name": p.backend_name}
            for p in enabled_social_providers()
        ],
        "local_login_enabled": LOCAL in settings.AUTH_PROVIDERS,
    }
