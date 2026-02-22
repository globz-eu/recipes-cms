from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from home.models import HomePage

from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase


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

    def tearDown(self):
        """Clean up test data after each test."""
        if self.homepage and self.homepage.pk:
            self.homepage.delete()

    def test_list_homepages(self):
        """Test listing all HomePage instances."""
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

    def test_retrieve_homepage(self):
        """Test retrieving a specific HomePage instance."""
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Home")
        self.assertEqual(response.data["description"], "Test home page description")

    def test_homepage_with_no_description(self):
        """Test HomePage without description field."""
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
        url = reverse("home-detail", kwargs={"pk": 99999})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_not_allowed(self):
        """Test that POST requests are not allowed (read-only viewset)."""
        url = reverse("home-list")
        data = {"title": "New Home", "description": "Should not be created"}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_put_not_allowed(self):
        """Test that PUT requests are not allowed (read-only viewset)."""
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        data = {"title": "Updated Home", "description": "Should not be updated"}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_not_allowed(self):
        """Test that PATCH requests are not allowed (read-only viewset)."""
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        data = {"description": "Should not be updated"}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        """Test that DELETE requests are not allowed (read-only viewset)."""
        url = reverse("home-detail", kwargs={"pk": self.homepage.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
