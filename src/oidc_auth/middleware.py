"""Turn refused social logins into a message and a redirect."""

import logging
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from oidc_auth.exceptions import LoginRefused
from oidc_auth.redirects import safe_redirect_url

logger = logging.getLogger(__name__)


def _with_auth_error(url: str, code: str) -> str:
    parts = urlsplit(url)
    extra = urlencode({"auth_error": code})
    query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit(parts._replace(query=query))


class LoginRefusedMiddleware:
    """
    Handle LoginRefused raised by the social auth pipeline.

    Stores the user-facing message and redirects back to the ``next`` URL given
    at login start (with ``auth_error=<code>`` appended) when it is safe,
    otherwise to the Wagtail admin login page.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(
        self, request: HttpRequest, exception: Exception
    ) -> HttpResponse | None:
        if not isinstance(exception, LoginRefused):
            return None

        logger.info(
            "Refused %s login: %s",
            getattr(exception.backend, "name", "unknown"),
            exception.code,
        )
        messages.error(request, exception.message)
        target = safe_redirect_url(request, request.session.pop("next", None))
        if target:
            return HttpResponseRedirect(_with_auth_error(target, exception.code))
        return HttpResponseRedirect(reverse("wagtailadmin_login"))
