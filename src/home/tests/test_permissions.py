from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory, TestCase
from rest_framework.exceptions import PermissionDenied

from home.permissions import IsEditorOrAdmin

User = get_user_model()


class IsEditorOrAdminPermissionTests(TestCase):
    """Tests for the IsEditorOrAdmin permission class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.permission = IsEditorOrAdmin()
        self.mock_view = Mock()

        # Create an Editors group
        self.editors_group, _ = Group.objects.get_or_create(name="Editors")

        # Create different types of users
        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", password="testpass123"
        )
        self.editor_user.groups.add(self.editors_group)

        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

        self.superuser = User.objects.create_superuser(
            username="superuser", email="super@test.com", password="testpass123"
        )

        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="testpass123"
        )

    def test_editor_user_has_permission(self):
        """Test that users in the Editors group have permission."""
        request = self.factory.get("/")
        request.user = self.editor_user

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertTrue(has_permission)

    def test_admin_user_has_permission(self):
        """Test that staff users have permission."""
        request = self.factory.get("/")
        request.user = self.admin_user

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertTrue(has_permission)

    def test_superuser_has_permission(self):
        """Test that superusers have permission."""
        request = self.factory.get("/")
        request.user = self.superuser

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertTrue(has_permission)

    def test_regular_user_gets_no_access_error(self):
        """Authenticated users without a role get a no_access PermissionDenied."""
        request = self.factory.get("/")
        request.user = self.regular_user

        with self.assertRaises(PermissionDenied) as ctx:
            self.permission.has_permission(request, self.mock_view)

        self.assertEqual(ctx.exception.detail["code"], "no_access")

    def test_unauthenticated_user_no_permission(self):
        """Test that unauthenticated users do not have permission."""
        request = self.factory.get("/")
        request.user = AnonymousUser()

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertFalse(has_permission)

    def test_request_without_user_no_permission(self):
        """Test that requests without a user attribute do not have permission."""
        request = self.factory.get("/")
        # Remove the user attribute to simulate edge case
        if hasattr(request, "user"):
            delattr(request, "user")

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertFalse(has_permission)


class NoAccessResponseTests(TestCase):
    """The API answers authenticated users without a role with code no_access."""

    def test_authenticated_user_without_role_gets_no_access_code(self):
        user = User.objects.create_user(username="norole", password="testpass123")
        self.client.force_login(user)

        response = self.client.get("/api/home/")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "no_access")

    def test_anonymous_user_does_not_get_no_access_code(self):
        response = self.client.get("/api/home/")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("code", response.json())

    def test_editor_gets_through(self):
        user = User.objects.create_user(username="ed", password="testpass123")
        user.groups.add(Group.objects.get_or_create(name="Editors")[0])
        self.client.force_login(user)

        response = self.client.get("/api/home/")

        self.assertEqual(response.status_code, 200)

    def test_moderator_gets_through(self):
        user = User.objects.create_user(username="mod", password="testpass123")
        user.groups.add(Group.objects.get_or_create(name="Moderators")[0])
        self.client.force_login(user)

        response = self.client.get("/api/home/")

        self.assertEqual(response.status_code, 200)

    def test_user_in_unmapped_group_gets_no_access_code(self):
        user = User.objects.create_user(username="rev", password="testpass123")
        user.groups.add(Group.objects.get_or_create(name="Reviewers")[0])
        self.client.force_login(user)

        response = self.client.get("/api/home/")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "no_access")
