from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()

FRONTEND_ORIGIN = "https://static.example.com"


class CsrfTokenViewTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.editor = User.objects.create_user(username="editor", password="pw")
        editors, _ = Group.objects.get_or_create(name="Editors")
        self.editor.groups.add(editors)

    def _get_token(self) -> str:
        response = self.client.get(reverse("api-csrf"))
        self.assertEqual(response.status_code, 200)
        return response.json()["csrfToken"]

    def test_returns_token_and_sets_cookie(self):
        response = self.client.get(reverse("api-csrf"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["csrfToken"])
        self.assertIn("csrftoken", response.cookies)

    def test_is_available_to_anonymous_users(self):
        response = self.client.get(reverse("api-csrf"))

        self.assertEqual(response.status_code, 200)

    @override_settings(CORS_ALLOWED_ORIGINS=[FRONTEND_ORIGIN])
    def test_cors_headers_for_frontend_origin(self):
        response = self.client.get(reverse("api-csrf"), HTTP_ORIGIN=FRONTEND_ORIGIN)

        self.assertEqual(response["Access-Control-Allow-Origin"], FRONTEND_ORIGIN)

    def test_authenticated_unsafe_request_without_token_is_rejected(self):
        self.client.force_login(self.editor)

        response = self.client.post(reverse("home-list"), {})

        self.assertEqual(response.status_code, 403)
        self.assertIn("CSRF", response.json()["detail"])

    def test_authenticated_unsafe_request_with_token_passes_csrf(self):
        self.client.force_login(self.editor)
        token = self._get_token()

        response = self.client.post(reverse("home-list"), {}, HTTP_X_CSRFTOKEN=token)

        # CSRF passed; the read-only viewset then rejects the method itself.
        self.assertEqual(response.status_code, 405)

    @override_settings(CSRF_TRUSTED_ORIGINS=[FRONTEND_ORIGIN])
    def test_unsafe_request_from_trusted_origin_passes_csrf(self):
        self.client.force_login(self.editor)
        token = self._get_token()

        response = self.client.post(
            reverse("home-list"),
            {},
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
            secure=True,
        )

        self.assertEqual(response.status_code, 405)

    def test_unsafe_request_from_untrusted_origin_is_rejected(self):
        self.client.force_login(self.editor)
        token = self._get_token()

        response = self.client.post(
            reverse("home-list"),
            {},
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN=FRONTEND_ORIGIN,
            secure=True,
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("CSRF", response.json()["detail"])
