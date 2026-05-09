from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings

from auth0_auth.views import CustomLogoutView

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

    @patch("auth0_auth.views.logout")
    def test_regular_logout_get_request(self, mock_logout):
        """Test regular logout for non-social auth user with GET request."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("auth0_auth.views.logout")
    def test_regular_logout_post_request(self, mock_logout):
        """Test regular logout for non-social auth user with POST request."""
        request = self.factory.post("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("auth0_auth.views.logout")
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
    @patch("auth0_auth.views.logout")
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
    @patch("auth0_auth.views.logout")
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

    @override_settings(
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=None,
        SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="test-client-id",
    )
    @patch("auth0_auth.views.logout")
    def test_auth0_logout_without_domain_configured(self, mock_logout):
        """Test logout when Auth0 domain is not configured."""
        request = self.factory.get("/admin/logout/")
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
            with override_settings(SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=None):
                response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("auth0_auth.views.logout")
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

    @patch("auth0_auth.views.logout")
    def test_social_auth_exception_handling(self, mock_logout):
        """Test that exceptions during social auth logout are handled gracefully."""
        request = self.factory.get("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        # Mock social_auth to raise an exception
        mock_social_queryset = Mock()
        mock_social_queryset.first.side_effect = Exception("Test exception")

        with patch.object(
            type(request.user), "social_auth", mock_social_queryset, create=True
        ):
            response = self.view(request)

        # Should fall back to regular logout despite exception
        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], settings.LOGOUT_REDIRECT_URL)

    @patch("auth0_auth.views.logout")
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
