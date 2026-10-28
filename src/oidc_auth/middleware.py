"""Turn refused social logins into a message and a redirect."""

import logging
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from social_core.exceptions import AuthAlreadyAssociated, AuthCanceled, AuthForbidden

from oidc_auth.exceptions import AlreadySignedIn, LoginRefused
from oidc_auth.redirects import safe_redirect_url

logger = logging.getLogger(__name__)


LOGIN_FAILED_CODE = "login_failed"
LOGIN_FAILED_MESSAGE = "Sign-in failed. Please try again."


def _refusal(exception: Exception) -> tuple[str, str] | None:
    """Return (code, message) for exceptions that end a social login, else None."""
    if isinstance(exception, LoginRefused):
        return exception.code, exception.message
    if isinstance(exception, AuthAlreadyAssociated):
        return AlreadySignedIn.code, AlreadySignedIn.message
    if isinstance(exception, AuthCanceled | AuthForbidden):
        return LOGIN_FAILED_CODE, LOGIN_FAILED_MESSAGE
    return None


def _with_auth_error(url: str, code: str) -> str:
    parts = urlsplit(url)
    extra = urlencode({"auth_error": code})
    query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit(parts._replace(query=query))


class LoginRefusedMiddleware:
    """
    Handle LoginRefused and other social-auth login failures.

    Besides our own LoginRefused this covers AuthAlreadyAssociated (the identity
    belongs to another user, reported as ``already_signed_in``) and AuthCanceled /
    AuthForbidden (reported as the generic ``login_failed``).

    Redirects back to the ``next`` URL given at login start (with
    ``auth_error=<code>`` appended) when it is safe. Otherwise stores the
    user-facing message and redirects to the Wagtail admin login page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> HttpResponse | None:
        refusal = _refusal(exception)
        if refusal is None:
            return None
        code, message = refusal

        logger.info(
            "Refused %s login: %s",
            getattr(getattr(exception, "backend", None), "name", "unknown"),
            code,
        )
        target = safe_redirect_url(request, request.session.pop("next", None))
        if target:
            return HttpResponseRedirect(_with_auth_error(target, code))
        messages.error(request, message)
        return HttpResponseRedirect(reverse("wagtailadmin_login"))
