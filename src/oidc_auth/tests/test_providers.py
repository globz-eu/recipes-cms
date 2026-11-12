from urllib.parse import parse_qs, urlsplit

from django.test import SimpleTestCase, override_settings

from oidc_auth.providers import auth0_logout_endpoint, auth0_logout_url

RETURN_TO = "https://app.example.com/frontend/?auth_error=email_unverified"


@override_settings(
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="tenant.auth0.com",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="client-1",
)
class Auth0LogoutTests(SimpleTestCase):
    def assert_logout_url(self, url):
        parts = urlsplit(url)
        self.assertEqual(
            (parts.scheme, parts.netloc, parts.path),
            ("https", "tenant.auth0.com", "/v2/logout"),
        )
        self.assertEqual(
            parse_qs(parts.query),
            {"client_id": ["client-1"], "returnTo": [RETURN_TO]},
        )

    def test_endpoint_builds_logout_url(self):
        self.assert_logout_url(auth0_logout_endpoint(RETURN_TO))

    def test_logout_url_builds_the_same_url(self):
        self.assert_logout_url(auth0_logout_url(None, None, RETURN_TO))
