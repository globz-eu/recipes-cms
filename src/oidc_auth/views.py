import logging

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View

from oidc_auth.providers import provider_for_backend
from oidc_auth.redirects import safe_redirect_url

logger = logging.getLogger(__name__)


class CustomLogoutView(View):
    """
    Logs out of Django/Wagtail and, for users who signed in through a social
    provider, redirects to that provider's own logout endpoint.
    """

    redirect_url: str | None = None

    def get_redirect_url(self, request: HttpRequest) -> str:
        return (
            safe_redirect_url(request, request.GET.get("next"))
            or self.redirect_url
            or settings.LOGOUT_REDIRECT_URL
        )

    def get(self, request: HttpRequest) -> HttpResponse:
        logger.info("CustomLogoutView GET: logging out user %s", request.user)
        if not request.user.is_authenticated:
            return redirect(self.get_redirect_url(request))
        redirect_url = self.get_redirect_url(request)
        social = request.user.social_auth.first()
        provider = provider_for_backend(social.provider) if social else None
        if provider is None:
            logger.info("No social provider for user, performing regular logout")
            logout(request)
            return redirect(redirect_url)
        logout_url = provider.logout_url(
            request, social, request.build_absolute_uri(redirect_url)
        )
        logout(request)
        logger.info("Redirecting to %s logout", provider.label)
        return redirect(logout_url)

    def post(self, request: HttpRequest) -> HttpResponse:
        logger.info(f"CustomLogoutView POST: request received for user: {request.user}")
        return self.get(request)
