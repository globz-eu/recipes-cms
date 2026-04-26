from typing import TYPE_CHECKING, Iterable
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.test import APITestCase

from image_auth.views import get_image_file, get_image_type

User = get_user_model()

RENDITION_URI = "/media/images/test.jpg"
ORIGINAL_URI = "/media/original_images/test.jpg"
INVALID_URI = "/media/other/test.jpg"


def _make_s3_client_mock(body: bytes = b"imagedata", content_type: str = "image/jpeg"):
    """Return a mock boto3 S3 client whose get_object returns the given body."""
    mock_body = MagicMock()
    mock_body.read.side_effect = [
        body,
        b"",
    ]  # first read returns data, second signals EOF
    mock_client = MagicMock()
    mock_client.get_object.return_value = {
        "Body": mock_body,
        "ContentType": content_type,
    }
    return mock_client


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "GetObject")


class MediaAccessPermissionTests(APITestCase):
    """Tests for MediaAccessPermission via the serve_media view."""

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
    # Image path validation
    # ------------------------------------------------------------------

    def test_invalid_image_path_returns_403(self):
        """URI whose path doesn't start with images/ or original_images/ returns 403."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(INVALID_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Image not found in DB
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=False)
    def test_image_not_found_returns_403(self, _mock):
        """When image does not exist in DB, returns 403."""
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Authorization checks (image exists in DB)
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_unauthenticated_user_returns_403(self, _mock):
        """Unauthenticated request is rejected with 403 (session auth has no WWW-Authenticate header)."""
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("image_auth.views.get_db_image", return_value=True)
    def test_regular_user_returns_403(self, _mock):
        """A user who is not superuser, staff, or editor receives 403."""
        self.client.login(username="regular", password="testpass123")
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_superuser_can_access(self, mock_s3, _mock_db):
        """Superuser can access the image."""
        mock_s3.return_value = _make_s3_client_mock()
        self.client.login(username="superuser", password="testpass123")
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_staff_user_can_access(self, mock_s3, _mock_db):
        """Staff user can access the image."""
        mock_s3.return_value = _make_s3_client_mock()
        self.client.login(username="staff", password="testpass123")
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_editor_user_can_access(self, mock_s3, _mock_db):
        """Editor group member can access the image."""
        mock_s3.return_value = _make_s3_client_mock()
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(RENDITION_URI)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_original_image_uri_accessible_for_editor(self, mock_s3, _mock_db):
        """Original image URI (original_images/ prefix) is also handled correctly."""
        mock_s3.return_value = _make_s3_client_mock()
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(ORIGINAL_URI)
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


class ServeMediaViewTests(APITestCase):
    """Tests for the serve_media view streaming behaviour."""

    RENDITION_URL = "/media/images/test.jpg"
    ORIGINAL_URL = "/media/original_images/test.jpg"
    MISSING_URL = "/media/images/missing.jpg"

    def setUp(self):
        editors_group, _ = Group.objects.get_or_create(name="Editors")
        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", password="testpass123"
        )
        self.editor_user.groups.add(editors_group)

    # ------------------------------------------------------------------
    # Successful streaming
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_rendition_streams_body(self, mock_get_client, _mock_db):
        """A valid rendition path returns 200 and the S3 body."""
        mock_get_client.return_value = _make_s3_client_mock(b"pixels", "image/jpeg")
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(self.RENDITION_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assert isinstance(response, StreamingHttpResponse)
        content = response.streaming_content
        if TYPE_CHECKING:
            assert isinstance(content, Iterable)
        self.assertEqual(b"".join(content), b"pixels")
        self.assertIn("image/jpeg", response["Content-Type"])

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_original_image_streams_body(self, mock_get_client, _mock_db):
        """A valid original_images path returns 200 and the S3 body."""
        mock_get_client.return_value = _make_s3_client_mock(b"rawpixels", "image/png")
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(self.ORIGINAL_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assert isinstance(response, StreamingHttpResponse)
        content = response.streaming_content
        if TYPE_CHECKING:
            assert isinstance(content, Iterable)
        self.assertEqual(b"".join(content), b"rawpixels")
        self.assertIn("image/png", response["Content-Type"])

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_correct_s3_key_is_requested(self, mock_get_client, _mock_db):
        """The S3 GetObject call uses the bare key (without /media/ prefix)."""
        mock_client = _make_s3_client_mock()
        mock_get_client.return_value = mock_client
        self.client.login(username="editor", password="testpass123")
        self.client.get(self.RENDITION_URL)
        mock_client.get_object.assert_called_once_with(
            Bucket=mock_client.get_object.call_args.kwargs["Bucket"],
            Key="images/test.jpg",
        )

    # ------------------------------------------------------------------
    # 404 handling
    # ------------------------------------------------------------------

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_no_such_key_returns_404(self, mock_get_client, _mock_db):
        """ClientError with NoSuchKey results in 404."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("NoSuchKey")
        mock_get_client.return_value = mock_client
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(self.MISSING_URL)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("image_auth.views.get_db_image", return_value=True)
    @patch("image_auth.views._get_s3_client")
    def test_404_error_code_returns_404(self, mock_get_client, _mock_db):
        """ClientError with code '404' results in 404."""
        mock_client = MagicMock()
        mock_client.get_object.side_effect = _make_client_error("404")
        mock_get_client.return_value = mock_client
        self.client.login(username="editor", password="testpass123")
        response = self.client.get(self.MISSING_URL)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
