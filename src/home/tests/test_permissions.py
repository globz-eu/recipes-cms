from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, AnonymousUser
from unittest.mock import Mock
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

    def test_regular_user_no_permission(self):
        """Test that regular users without the Editors group do not have permission."""
        request = self.factory.get("/")
        request.user = self.regular_user

        has_permission = self.permission.has_permission(request, self.mock_view)
        self.assertFalse(has_permission)

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
