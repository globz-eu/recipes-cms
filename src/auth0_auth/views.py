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
                    logout_redirect_url = settings.LOGOUT_REDIRECT_URL
                    if not auth0_domain or not logout_redirect_url:
                        raise Exception(
                            "Auth0 settings not configured properly. Please set SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN and LOGOUT_REDIRECT_URL in your settings."
                        )
                    return_to = request.build_absolute_uri(logout_redirect_url)
                    params = {
                        "post_logout_redirect_uri": return_to,
                        "client_id": getattr(
                            settings, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY", ""
                        ),
                    }
                    logout_url = urlunparse(
                        (
                            "https",
                            auth0_domain,
                            "/oidc/logout",
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
                    logout(request)
                    return redirect(f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

            except Exception as e:
                logger.exception(f"Error during social auth logout: {e}")
                logger.info("Performing regular logout")
                logout(request)
                return redirect(f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")
        else:
            logger.info("No authenticated user found, redirecting to admin login")
            return redirect(f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

    def post(self, request: HttpRequest) -> HttpResponse:
        logger.info(f"CustomLogoutView POST: request received for user: {request.user}")
        return self.get(request)
