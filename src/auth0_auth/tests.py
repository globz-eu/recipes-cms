from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.sessions.middleware import SessionMiddleware
from unittest.mock import Mock, patch
from auth0_auth.views import CustomLogoutView
from auth0_auth.pipeline import add_user_to_editors_group
from django.conf import settings

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
        middleware = SessionMiddleware(lambda x: None)
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
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

    @patch("auth0_auth.views.logout")
    def test_regular_logout_post_request(self, mock_logout):
        """Test regular logout for non-social auth user with POST request."""
        request = self.factory.post("/admin/logout/")
        request.user = self.user
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_called_once()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

    @patch("auth0_auth.views.logout")
    def test_anonymous_user_logout(self, mock_logout):
        """Test logout with anonymous user."""
        request = self.factory.get("/admin/logout/")
        request.user = AnonymousUser()
        request = self._add_session_to_request(request)

        response = self.view(request)

        mock_logout.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

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
        self.assertIn("test-domain.auth0.com/oidc/logout", response.url)
        self.assertIn("post_logout_redirect_uri=", response.url)
        self.assertIn("client_id=test-client-id", response.url)

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
        self.assertIn("test-domain.auth0.com/oidc/logout", response.url)

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
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

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
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

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
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")

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
        self.assertEqual(response.url, f"/{settings.WAGTAIL_ADMIN_BASE_PATH}/")


class AddUserToEditorsGroupPipelineTestCase(TestCase):
    """Tests for the add_user_to_editors_group pipeline function."""

    def setUp(self):
        """Set up test fixtures."""
        self.backend = Mock()
        self.response = {}
        # Clean up any existing Editors group from previous tests
        Group.objects.filter(name="Editors").delete()

    def test_adds_new_user_to_editors_group(self):
        """Test that a newly created user is added to the Editors group."""
        user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )

        # Simulate pipeline kwargs for a new user
        kwargs = {"is_new": True}

        result = add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify the user was added to the Editors group
        self.assertTrue(user.groups.filter(name="Editors").exists())
        self.assertIsNone(result)  # Pipeline should return None

    def test_creates_editors_group_if_not_exists(self):
        """Test that the Editors group is created if it doesn't exist."""
        # Ensure no Editors group exists
        self.assertFalse(Group.objects.filter(name="Editors").exists())

        user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )

        kwargs = {"is_new": True}

        add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify the Editors group was created
        self.assertTrue(Group.objects.filter(name="Editors").exists())
        self.assertTrue(user.groups.filter(name="Editors").exists())

    def test_does_not_add_existing_user_to_group(self):
        """Test that existing users are not added to the Editors group."""
        user = User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="testpass123",
        )

        # Simulate pipeline kwargs for an existing user
        kwargs = {"is_new": False}

        result = add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify the user was NOT added to the Editors group
        self.assertFalse(user.groups.filter(name="Editors").exists())
        self.assertIsNone(result)

    def test_does_not_add_when_is_new_not_provided(self):
        """Test that users are not added when is_new is not in kwargs."""
        user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Kwargs without is_new
        kwargs = {}

        result = add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify the user was NOT added to the Editors group
        self.assertFalse(user.groups.filter(name="Editors").exists())
        self.assertIsNone(result)

    def test_handles_none_user(self):
        """Test that the function handles None user gracefully."""
        kwargs = {"is_new": True}

        # Should not raise an exception
        result = add_user_to_editors_group(self.backend, None, self.response, **kwargs)

        self.assertIsNone(result)

    def test_uses_existing_editors_group(self):
        """Test that the function uses an existing Editors group rather than creating a new one."""
        # Pre-create the Editors group
        existing_group = Group.objects.create(name="Editors")

        user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )

        kwargs = {"is_new": True}

        add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify only one Editors group exists
        self.assertEqual(Group.objects.filter(name="Editors").count(), 1)
        # Verify the user is in the existing group
        self.assertIn(existing_group, user.groups.all())

    @patch("auth0_auth.pipeline.Group.objects.get_or_create")
    def test_handles_exception_gracefully(self, mock_get_or_create):
        """Test that exceptions are caught and logged."""
        user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )

        # Make get_or_create raise an exception
        mock_get_or_create.side_effect = Exception("Database error")

        kwargs = {"is_new": True}

        # Should not raise an exception
        result = add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        self.assertIsNone(result)

    def test_user_can_be_in_multiple_groups(self):
        """Test that adding to Editors doesn't affect other group memberships."""
        user = User.objects.create_user(
            username="newuser", email="new@example.com", password="testpass123"
        )

        # Add user to another group first
        other_group, _ = Group.objects.get_or_create(name="Moderators")
        user.groups.add(other_group)

        kwargs = {"is_new": True}

        add_user_to_editors_group(self.backend, user, self.response, **kwargs)

        # Verify user is in both groups
        self.assertEqual(user.groups.count(), 2)
        self.assertTrue(user.groups.filter(name="Editors").exists())
        self.assertTrue(user.groups.filter(name="Moderators").exists())
