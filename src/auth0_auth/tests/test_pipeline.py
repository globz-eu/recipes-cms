from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from unittest.mock import Mock, patch
from auth0_auth.pipeline import add_user_to_editors_group

User = get_user_model()


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
