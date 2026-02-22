from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APITestCase

from home.models import HomePage

from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

User = get_user_model()


class HomeSetUpTests(WagtailPageTestCase):
    """
    Tests for basic page structure setup and HomePage creation.
    """

    def test_root_create(self):
        root_page = Page.objects.get(pk=1)
        self.assertIsNotNone(root_page)

    def test_homepage_create(self):
        root_page = Page.objects.get(pk=1)
        homepage = HomePage(title="Home")
        root_page.add_child(instance=homepage)
        self.assertTrue(HomePage.objects.filter(title="Home").exists())


class HomeViewSetTests(APITestCase):
    """
    Tests for HomeViewSet API endpoints.
    """

    def setUp(self):
        """Set up test data."""
        root_page = Page.objects.get(pk=1)
        self.homepage = HomePage(
            title="Test Home", description="Test home page description"
        )
        root_page.add_child(instance=self.homepage)
        self.homepage.save()

        # Create users with different permissions
        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", password="testpass123"
        )
        self.editors_group, _ = Group.objects.get_or_create(name="Editors")
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

    def tearDown(self):
        """Clean up test data after each test."""
        if self.homepage and self.homepage.pk:
            self.homepage.delete()

    def test_list_homepages_as_editor(self):
        """Test listing all HomePage instances as editor user."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

        # Verify our test homepage is in the list
        titles = [page["title"] for page in response.data]
        self.assertIn("Test Home", titles)

        # Verify the test homepage data
        test_home = next(page for page in response.data if page["title"] == "Test Home")
        self.assertEqual(test_home["description"], "Test home page description")

    def test_list_homepages_as_admin(self):
        """Test listing all HomePage instances as admin user."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("home-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_homepages_as_superuser(self):
        """Test listing all HomePage instances as superuser."""
        self.client.force_authenticate(user=self.superuser)
        url = reverse("home-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_list_homepages_unauthenticated(self):
        """Test that unauthenticated users cannot access the API."""
        url = reverse("home-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_homepages_as_regular_user(self):
        """Test that regular users (not in Editors group) cannot access the API."""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("home-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_homepage_as_editor(self):
        """Test retrieving a specific HomePage instance as editor."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Home")
        self.assertEqual(response.data["description"], "Test home page description")

    def test_retrieve_homepage_unauthenticated(self):
        """Test that unauthenticated users cannot retrieve a HomePage."""
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_homepage_with_no_description(self):
        """Test HomePage without description field."""
        self.client.force_authenticate(user=self.editor_user)
        root_page = Page.objects.get(pk=1)
        homepage_no_desc = HomePage(title="Home Without Description")
        root_page.add_child(instance=homepage_no_desc)
        homepage_no_desc.save()

        url = reverse("home-detail", kwargs={"pk": homepage_no_desc.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Home Without Description")
        self.assertIsNone(response.data["description"])

        # Clean up the additional homepage
        homepage_no_desc.delete()

    def test_homepage_not_found(self):
        """Test retrieving a non-existent HomePage."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-detail", kwargs={"pk": 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_not_allowed(self):
        """Test that POST requests are not allowed (read-only viewset)."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-list")
        data = {"title": "New Home", "description": "Should not be created"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_allowed(self):
        """Test that PUT requests are not allowed (read-only viewset)."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        data = {"title": "Updated Home", "description": "Should not be updated"}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_not_allowed(self):
        """Test that PATCH requests are not allowed (read-only viewset)."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        data = {"description": "Should not be updated"}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        """Test that DELETE requests are not allowed (read-only viewset)."""
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
