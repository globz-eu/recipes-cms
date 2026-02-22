from django.shortcuts import redirect
from django.contrib.auth import logout
from django.views import View
from django.conf import settings
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class CustomLogoutView(View):
    """
    Custom logout view that handles both Django/Wagtail and social_auth logout.
    For Auth0, redirects to Auth0's logout endpoint with return_to parameter.
    """

    def get(self, request):
        logger.info(f"CustomLogoutView GET: Initiating logout for user: {request.user}")

        # Check if user is authenticated via social_auth
        if request.user.is_authenticated:
            try:
                social = request.user.social_auth.first()
                logger.info(
                    "Social auth found: %s, provider: %s",
                    social,
                    social.provider if social else "N/A",
                )
                if social and social.provider == "auth0_openidconnect":
                    logger.info("Auth0 user detected, performing Auth0 logout")
                    # Perform Django logout first
                    logout(request)

                    try:
                        auth0_domain = settings.SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN
                        logout_redirect_url = settings.LOGOUT_REDIRECT_URL
                    except AttributeError:
                        raise Exception(
                            "Auth0 settings not configured properly. Please set SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN and LOGOUT_REDIRECT_URL in your settings."
                        )

                    # Get the return URL (where to redirect after Auth0 logout)
                    return_to = request.build_absolute_uri(logout_redirect_url)

                    # Auth0 logout endpoint
                    logout_url = f"https://{auth0_domain}/oidc/logout?"
                    params = {
                        "post_logout_redirect_uri": return_to,
                        "client_id": getattr(
                            settings, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY", ""
                        ),
                    }
                    logout_url += urlencode(params)
                    logger.info(f"Redirecting to Auth0 logout: {logout_url}")
                    return redirect(logout_url)

            except Exception as e:
                # If there's any issue with social auth, fall through to regular logout
                logger.exception(f"Error during social auth logout: {e}")

        # Regular logout for non-social auth users
        logger.info("Performing regular logout")
        logout(request)
        return redirect(f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

    def post(self, request):
        logger.info(f"CustomLogoutView POST: request received for user: {request.user}")
        return self.get(request)
