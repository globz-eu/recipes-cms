from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from social_django.models import UserSocialAuth

from oidc_auth.views import CustomLogoutView

User = get_user_model()


class CustomLogoutViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = CustomLogoutView.as_view()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def _add_session_to_request(self, request):
        """Add session to request for logout to work properly."""
        from django.http import HttpResponse

        middleware = SessionMiddleware(lambda x: HttpResponse())
        middleware.process_request(request)
        request.session.save()
        return request

    @patch("oidc_auth.views.logout")
    def test_regular_logout_get_request(self, mock_logout):
        """Test regular logout for non-social auth user with GET request."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("oidc_auth.views.logout")
    def test_regular_logout_post_request(self, mock_logout):
        """Test regular logout for non-social auth user with POST request."""
        request = self.factory.post("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("oidc_auth.views.logout")
    def test_anonymous_user_logout(self, mock_logout):
        """Test logout with anonymous user."""
        request = self.factory.get("/admin/logout/")
        request.user = AnonymousUser()
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @override_settings(
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="test-domain.auth0.com",
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="test-client-id",
    )
    @patch("oidc_auth.views.logout")
    def test_auth0_logout_with_social_auth(self, mock_logout):
        """Test logout for user authenticated via Auth0."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        # Mock social_auth
        mock_social = Mock()
        mock_social.provider = "auth0_openidconnect"
        mock_social_queryset = Mock()
        mock_social_queryset.first.return_value = mock_social
        mock_social_queryset.exists.return_value = True

        # Patch the user's social_auth property
        with patch.object(
            type(request.user), "social_auth", mock_social_queryset, create=True
        ):
            response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertIn("test-domain.auth0.com/v2/logout", response["Location"])
        self.assertIn("returnTo=", response["Location"])
        self.assertIn("client_id=test-client-id", response["Location"])

    @override_settings(
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="test-domain.auth0.com",
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="test-client-id",
    )
    @patch("oidc_auth.views.logout")
    def test_auth0_logout_post_request(self, mock_logout):
        """Test Auth0 logout with POST request."""
        request = self.factory.post("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        # Mock social_auth
        mock_social = Mock()
        mock_social.provider = "auth0_openidconnect"
        mock_social_queryset = Mock()
        mock_social_queryset.first.return_value = mock_social
        mock_social_queryset.exists.return_value = True

        with patch.object(
            type(request.user), "social_auth", mock_social_queryset, create=True
        ):
            response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertIn("test-domain.auth0.com/v2/logout", response["Location"])

    @patch("oidc_auth.views.logout")
    def test_social_auth_with_different_provider(self, mock_logout):
        """Test logout for user with social auth but not Auth0."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        # Mock social_auth with different provider
        mock_social = Mock()
        mock_social.provider = "google-oauth2"
        mock_social_queryset = Mock()
        mock_social_queryset.first.return_value = mock_social
        mock_social_queryset.exists.return_value = True

        with patch.object(
            type(request.user), "social_auth", mock_social_queryset, create=True
        ):
            response = self.view(request)

        # Should fall back to regular logout
        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("oidc_auth.views.logout")
    def test_no_social_auth_attribute(self, mock_logout):
        """Test logout when user has no social_auth attribute."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        # User without social_auth should fall back to regular logout
        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("oidc_auth.views.logout")
    def test_relative_next_is_used(self, mock_logout):
        """A relative ?next URL on the current host is honoured."""
        request = self.factory.get("/admin/logout/", {"next": "/frontend/"})
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/frontend/")

    @override_settings(SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["static.example.com"])
    @patch("oidc_auth.views.logout")
    def test_absolute_next_on_allowed_host_is_used(self, mock_logout):
        """An absolute ?next URL on an allowed redirect host is honoured."""
        next_url = "http://static.example.com/frontend/"
        request = self.factory.get("/admin/logout/", {"next": next_url})
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], next_url)

    @override_settings(SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["static.example.com"])
    @patch("oidc_auth.views.logout")
    def test_absolute_next_on_disallowed_host_is_ignored(self, mock_logout):
        """An absolute ?next URL on an unknown host falls back to the default."""
        request = self.factory.get(
            "/admin/logout/", {"next": "https://evil.example.org/"}
        )
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @override_settings(
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="test-domain.auth0.com",
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="test-client-id",
        SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["static.example.com"],
    )
    @patch("oidc_auth.views.logout")
    def test_auth0_logout_return_to_allowed_absolute_next(self, mock_logout):
        """Auth0 returnTo uses an allowed absolute ?next URL unchanged."""
        next_url = "http://static.example.com/frontend/"
        request = self.factory.get("/admin/logout/", {"next": next_url})
        request.user = self.user
        request = self._add_session_to_request(request)

        mock_social = Mock()
        mock_social.provider = "auth0_openidconnect"
        mock_social_queryset = Mock()
        mock_social_queryset.first.return_value = mock_social

        with patch.object(
            type(request.user), "social_auth", mock_social_queryset, create=True
        ):
            response = self.view(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "returnTo=http%3A%2F%2Fstatic.example.com%2Ffrontend%2F",
            response["Location"],
        )


@override_settings(
    SOCIAL_AUTH_ZITADEL_DOMAIN="zitadel.example.com",
    SOCIAL_AUTH_ZITADEL_KEY="zit-client",
    SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["static.example.com"],
)
class ProviderLogoutTestCase(TestCase):
    def logout(self, user, extra_data=None, provider="zitadel", **query):
        if provider:
            UserSocialAuth.objects.create(
                user=user, provider=provider, uid="u1", extra_data=extra_data or {}
            )
        self.client.force_login(user)
        response = self.client.get("/admin/logout/", query)
        self.assertNotIn("_auth_user_id", self.client.session)
        return response

    def make_user(self, name="zuser"):
        return User.objects.create_user(username=name, email=f"{name}@example.com")

    def test_zitadel_logout_with_id_token(self):
        response = self.logout(self.make_user(), {"id_token": "tok.en"})
        url = urlsplit(response["Location"])
        query = parse_qs(url.query)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            (url.scheme, url.netloc, url.path),
            ("https", "zitadel.example.com", "/oidc/v1/end_session"),
        )
        self.assertEqual(query["client_id"], ["zit-client"])
        self.assertEqual(query["id_token_hint"], ["tok.en"])
        self.assertEqual(
            query["post_logout_redirect_uri"],
            ["http://testserver/admin/"],
        )

    def test_zitadel_logout_without_id_token(self):
        response = self.logout(self.make_user())
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertNotIn("id_token_hint", query)
        self.assertIn("post_logout_redirect_uri", query)

    def test_zitadel_logout_honours_safe_next(self):
        next_url = "http://static.example.com/frontend/"
        response = self.logout(self.make_user(), next=next_url)
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(query["post_logout_redirect_uri"], [next_url])

    def test_zitadel_logout_ignores_disallowed_next(self):
        response = self.logout(self.make_user(), next="https://evil.example.org/")
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(
            query["post_logout_redirect_uri"],
            ["http://testserver/admin/"],
        )

    def test_zitadel_logout_does_not_log_id_token(self):
        with self.assertLogs("oidc_auth.views", level="INFO") as logs:
            self.logout(self.make_user(), {"id_token": "secret.tok.en"})
        self.assertNotIn("secret.tok.en", "\n".join(logs.output))

    def test_local_user_gets_plain_logout(self):
        response = self.logout(self.make_user("local"), provider=None)
        self.assertEqual(response["Location"], "/admin/")

    def test_unknown_provider_gets_plain_logout(self):
        response = self.logout(self.make_user(), provider="google-oauth2")
        self.assertEqual(response["Location"], "/admin/")

    def test_unauthenticated_redirects_without_error(self):
        response = self.client.get("/admin/logout/")
        self.assertEqual(response["Location"], "/admin/")

    def test_malformed_next_does_not_error(self):
        response = self.logout(self.make_user("mal"), provider=None, next="http://[")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/admin/")
