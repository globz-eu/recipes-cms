"""Turn refused social logins into a message and a redirect."""

import logging
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from social_core.exceptions import AuthAssociationError, AuthException

from oidc_auth.exceptions import AlreadySignedIn, LoginRefused
from oidc_auth.redirects import safe_redirect_url

logger = logging.getLogger(__name__)


LOGIN_FAILED_CODE = "login_failed"
LOGIN_FAILED_MESSAGE = "Sign-in failed. Please try again."
# social_user's code for an identity linked to another user than the signed-in one.
IDENTITY_IN_USE_CODE = "identity_in_use"


def _refusal(exception: AuthException) -> tuple[str, str]:
    """Return the (code, message) reported for a social login that failed."""
    if isinstance(exception, LoginRefused):
        return exception.auth_error, exception.message
    if (
        isinstance(exception, AuthAssociationError)
        and exception.code == IDENTITY_IN_USE_CODE
    ):
        return AlreadySignedIn.auth_error, AlreadySignedIn.message
    return LOGIN_FAILED_CODE, LOGIN_FAILED_MESSAGE


def _with_auth_error(url: str, code: str) -> str:
    parts = urlsplit(url)
    extra = urlencode({"auth_error": code})
    query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit(parts._replace(query=query))


class LoginRefusedMiddleware:
    """
    Handle LoginRefused and other social-auth login failures.

    Besides our own LoginRefused this covers AuthAssociationError with code
    ``identity_in_use`` (the identity belongs to another user, reported as
    ``already_signed_in``) and every other AuthException such as AuthCanceled,
    AuthPolicyError, a lost session, a rejected credential or another
    association conflict (reported as the generic ``login_failed``).

    Redirects back to the ``next`` URL given at login start (with
    ``auth_error=<code>`` appended) when it is safe. Otherwise stores the
    user-facing message and redirects to the Wagtail admin login page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> HttpResponse | None:
        if not isinstance(exception, AuthException):
            return None
        code, message = _refusal(exception)

        backend_name = getattr(getattr(exception, "backend", None), "name", "unknown")
        if isinstance(exception, LoginRefused):
            logger.info("Refused %s login: %s", backend_name, code)
        else:
            # social_core keeps the provider's details out of str(exception).
            logger.warning(
                "Failed %s login: %s (%s %s: %s)",
                backend_name,
                code,
                type(exception).__name__,
                exception.code,
                exception.detail,
                exc_info=exception,
            )
        target = safe_redirect_url(request, request.session.pop("next", None))
        if target:
            return HttpResponseRedirect(_with_auth_error(target, code))
        messages.error(request, message)
        return HttpResponseRedirect(reverse("wagtailadmin_login"))
