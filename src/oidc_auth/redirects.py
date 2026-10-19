"""Validation of user-supplied redirect targets."""

import logging

from django.conf import settings
from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


def safe_redirect_url(request: HttpRequest, url: str | None) -> str | None:
    """
    Return ``url`` if it points to the request host or an allowed redirect host.

    Allowed hosts are the request host plus SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS;
    HTTPS is required when the request itself is secure. Rejected URLs are
    logged and ``None`` is returned.
    """
    if not url:
        return None
    allowed_hosts = {
        request.get_host(),
        *getattr(settings, "SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS", []),
    }
    if url_has_allowed_host_and_scheme(
        url, allowed_hosts=allowed_hosts, require_https=request.is_secure()
    ):
        return url
    logger.warning("Ignoring disallowed redirect: %s", url)
    return None
