import logging
from urllib.parse import urlencode, urlunparse

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View

logger = logging.getLogger(__name__)


class CustomLogoutView(View):
    """
    Custom logout view that handles both Django/Wagtail and social_auth logout.
    For Auth0, redirects to Auth0's logout endpoint with return_to parameter.
    """

    redirect_url: str | None = None

    def get_redirect_url(self, request: HttpRequest) -> str:
        return (
            request.GET.get("next") or self.redirect_url or settings.LOGOUT_REDIRECT_URL
        )

    def get(self, request: HttpRequest) -> HttpResponse:
        logger.info(f"CustomLogoutView GET: Initiating logout for user: {request.user}")
        if request.user.is_authenticated:
            try:
                social_auth = getattr(request.user, "social_auth", None)
                social = social_auth.first() if social_auth else None
                logger.info(
                    "Social auth found: %s, provider: %s",
                    social,
                    social.provider if social else "N/A",
                )
                if social and social.provider == "auth0_openidconnect":
                    logger.info("Auth0 user detected, performing Auth0 logout")
                    auth0_domain = settings.SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN
                    if not auth0_domain:
                        raise Exception(
                            "Auth0 settings not configured properly. Please set SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN in your settings."
                        )
                    return_to = request.build_absolute_uri(
                        self.get_redirect_url(request)
                    )
                    params = {
                        "client_id": getattr(
                            settings, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY", ""
                        ),
                        "returnTo": return_to,
                    }
                    logout_url = urlunparse(
                        (
                            "https",
                            auth0_domain,
                            "/v2/logout",
                            "",
                            urlencode(params),
                            "",
                        )
                    )
                    logger.info("Logging out user from Django session")
                    logout(request)
                    logger.info(f"Redirecting to Auth0 logout: {logout_url}")
                    return redirect(logout_url)
                else:
                    logger.info("Non-Auth0 user, performing regular logout")
                    redirect_url = self.get_redirect_url(request)
                    logout(request)
                    return redirect(redirect_url)

            except Exception as e:
                logger.exception(f"Error during social auth logout: {e}")
                logger.info("Performing regular logout")
                redirect_url = self.get_redirect_url(request)
                logout(request)
                return redirect(redirect_url)
        else:
            logger.info("No authenticated user found, redirecting to admin login")
            return redirect(self.get_redirect_url(request))

    def post(self, request: HttpRequest) -> HttpResponse:
        logger.info(f"CustomLogoutView POST: request received for user: {request.user}")
        return self.get(request)
