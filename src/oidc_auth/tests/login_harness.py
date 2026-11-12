"""Complete a social login through the real callback URL with canned claims."""

from unittest.mock import patch
from urllib.parse import urlencode

NEXT = "/frontend/"


def auth0_logout_location(domain, return_to, client_id="key"):
    """The Auth0 ``/v2/logout`` redirect expected after a refused Auth0 login."""
    query = urlencode({"client_id": client_id, "returnTo": return_to})
    return f"https://{domain}/v2/logout?{query}"


def complete_login(client, backend_class, claims, next_url=NEXT):
    """GET the backend's callback with ``claims`` as the provider's user data."""
    session = client.session
    if next_url:
        session["next"] = next_url
    session.save()

    def auth_complete(backend, *args, **kwargs):
        return backend.do_auth("access-token", *args, **kwargs)

    with (
        patch.object(backend_class, "auth_complete", auth_complete),
        patch.object(backend_class, "user_data", lambda *a, **k: dict(claims)),
    ):
        return client.get(f"/complete/{backend_class.name}/")
