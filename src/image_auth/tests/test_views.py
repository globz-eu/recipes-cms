from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APITestCase

from image_auth.views import get_image_file, get_image_type

User = get_user_model()

IMAGE_AUTH_URL = "/api/image-auth/"
RENDITION_URI = "/media/images/test.jpg"
ORIGINAL_URI = "/media/original_images/test.jpg"
INVALID_URI = "/media/other/test.jpg"


class CheckPermissionsViewTests(APITestCase):
    """Tests for the check_permissions view."""

    def setUp(self):
        self.editors_group, _ = Group.objects.get_or_create(name="Editors")

        self.superuser = User.objects.create_superuser(
            username="superuser", email="super@test.com", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", password="testpass123"
        )
        self.editor_user.groups.add(self.editors_group)

        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="testpass123"
        )

    # ------------------------------------------------------------------
    # Header validation
    # ------------------------------------------------------------------

    def test_missing_x_original_uri_returns_403(self):
        """Request without X-Original-Uri header returns 403."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["message"], "Forbidden")

    def test_invalid_image_path_returns_403(self):
        """URI whose path doesn't start with images/ or original_images/ returns 403."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=INVALID_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["message"], "Forbidden")

    # ------------------------------------------------------------------
    # Image not found in DB
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=False)
    def test_image_not_found_returns_403(self, _mock):
        """When image does not exist in DB, returns 403."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["message"], "Forbidden")

    # ------------------------------------------------------------------
    # Authorization checks (image exists in DB)
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_unauthenticated_user_returns_401(self, _mock):
        """Unauthenticated request is rejected with 401."""
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], "Unauthorized")

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_regular_user_returns_401(self, _mock):
        """A user who is not superuser, staff, or editor receives 401."""
        self.client.login(username="regular", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["message"], "Unauthorized")

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_superuser_returns_200(self, _mock):
        """Superuser can access the image."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["message"], "OK")

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_staff_user_returns_200(self, _mock):
        """Staff user can access the image."""
        self.client.login(username="staff", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["message"], "OK")

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_editor_user_returns_200(self, _mock):
        """Editor group member can access the image."""
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["message"], "OK")

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_original_image_uri_returns_200_for_editor(self, _mock):
        """Original image URI (original_images/ prefix) is also handled correctly."""
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(IMAGE_AUTH_URL, HTTP_X_ORIGINAL_URI=ORIGINAL_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ------------------------------------------------------------------
    # Helper function unit tests
    # ------------------------------------------------------------------


class GetImageFileTests(APITestCase):
    """Unit tests for the get_image_file helper."""

    def test_strips_media_prefix(self):
        result = get_image_file("/media/images/photo.jpg")
        self.assertEqual(result, "images/photo.jpg")

    def test_strips_media_url_prefix_original(self):
        result = get_image_file("/media/original_images/photo.jpg")
        self.assertEqual(result, "original_images/photo.jpg")

    def test_no_prefix_returns_unchanged(self):
        result = get_image_file("images/photo.jpg")
        self.assertEqual(result, "images/photo.jpg")


class GetImageTypeTests(APITestCase):
    """Unit tests for the get_image_type helper."""

    def test_rendition_prefix_returns_rendition(self):
        self.assertEqual(get_image_type("images/photo.jpg"), "rendition")

    def test_original_prefix_returns_original(self):
        self.assertEqual(get_image_type("original_images/photo.jpg"), "original")

    def test_unknown_prefix_returns_none(self):
        self.assertIsNone(get_image_type("other/photo.jpg"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(get_image_type(""))
