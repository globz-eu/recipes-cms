"""Turn refused social logins into a message and a redirect."""

import logging
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from social_core.exceptions import AuthAssociationError, AuthException

from oidc_auth.config import AUTH0
from oidc_auth.exceptions import AlreadySignedIn, LoginRefused
from oidc_auth.providers import PROVIDERS, auth0_logout_endpoint
from oidc_auth.redirects import safe_redirect_url

logger = logging.getLogger(__name__)


LOGIN_FAILED_CODE = "login_failed"
LOGIN_FAILED_MESSAGE = "Sign-in failed. Please try again."
# social_user's code for an identity linked to another user than the signed-in one.
IDENTITY_IN_USE_CODE = "identity_in_use"
# The only frontend path registered as an Auth0 logout returnTo (hash routing).
FRONTEND_PATH = "/frontend/"
SOCIAL_COMPLETE_VIEW = "social:complete"


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


def _log_failure(exception: AuthException, backend_name: str, code: str) -> None:
    if isinstance(exception, LoginRefused):
        logger.info("Refused %s login: %s", backend_name, code)
        return
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


def _failed_backend_name(request: HttpRequest, exception: AuthException) -> str | None:
    """Name of the social backend whose login failed, or None if unknown."""
    for backend in (
        getattr(exception, "backend", None),
        getattr(request, "backend", None),
    ):
        name = getattr(backend, "name", None)
        if isinstance(name, str):
            return name
    match = request.resolver_match
    if match and match.view_name == SOCIAL_COMPLETE_VIEW:
        backend_name = match.kwargs.get("backend")
        if isinstance(backend_name, str):
            return backend_name
    return None


def _is_auth0(backend_name: str | None) -> bool:
    return (
        backend_name == PROVIDERS[AUTH0].backend_name
        and AUTH0 in settings.AUTH_PROVIDERS
    )


def _auth0_return_to(
    request: HttpRequest, target: str | None, refusal: tuple[str, str]
) -> str:
    """
    Absolute Auth0 ``returnTo``: a safe frontend target with ``auth_error``.

    Any other target falls back to the admin home, with the message stored,
    because Auth0 only accepts registered paths.
    """
    code, message = refusal
    if target and urlsplit(target).path == FRONTEND_PATH:
        return request.build_absolute_uri(_with_auth_error(target, code))
    messages.error(request, message)
    return request.build_absolute_uri(reverse("wagtailadmin_home"))


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

    A failed Auth0 login also ends the Auth0 session through its logout
    endpoint, so the next attempt shows Auth0's login page again.
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
        backend_name = _failed_backend_name(request, exception)
        _log_failure(exception, backend_name or "unknown", code)
        target = safe_redirect_url(request, request.session.pop("next", None))
        if _is_auth0(backend_name):
            return_to = _auth0_return_to(request, target, (code, message))
            return HttpResponseRedirect(auth0_logout_endpoint(return_to))
        if target:
            return HttpResponseRedirect(_with_auth_error(target, code))
        messages.error(request, message)
        return HttpResponseRedirect(reverse("wagtailadmin_login"))
