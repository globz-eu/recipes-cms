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
        logger.info(
            "CustomLogoutView GET: Initiating logout for user: %s", request.user
        )
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

                    # Build Auth0 logout URL
                    auth0_domain = getattr(
                        settings, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN", None
                    )
                    if auth0_domain:
                        # Get the return URL (where to redirect after Auth0 logout)
                        return_to = request.build_absolute_uri("/admin/logout/")

                        # Auth0 logout endpoint
                        logout_url = f"https://{auth0_domain}/oidc/logout?"
                        params = {
                            "post_logout_redirect_uri": return_to,
                            "client_id": getattr(
                                settings, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY", ""
                            ),
                        }
                        logout_url += urlencode(params)
                        logger.info("Redirecting to Auth0 logout: %s", logout_url)
                        return redirect(logout_url)
                    else:
                        logger.warning("Auth0 domain not configured")
            except Exception as e:
                # If there's any issue with social auth, fall through to regular logout
                logger.exception("Error during social auth logout: %s", e)

        # Regular logout for non-social auth users
        logger.info("Performing regular logout")
        logout(request)
        return redirect("/admin/")

    def post(self, request):
        logger.info(
            "CustomLogoutView POST: request received for user: %s", request.user
        )
        return self.get(request)
