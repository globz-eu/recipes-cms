from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()

PASSWORD = "a-long-and-uncommon-passphrase"


class DevLoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="editor", password=PASSWORD)
        self.url = reverse("api-dev-login")

    def _post(self, **data):
        return self.client.post(self.url, data, content_type="application/json")

    @override_settings(DEV_PASSWORD_LOGIN=False)
    def test_disabled_returns_404(self):
        response = self._post(username="editor", password=PASSWORD)

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEV_PASSWORD_LOGIN=True)
    def test_valid_credentials_start_a_session(self):
        response = self._post(username="editor", password=PASSWORD)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "editor"})
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    @override_settings(DEV_PASSWORD_LOGIN=True)
    def test_wrong_password_is_rejected(self):
        response = self._post(username="editor", password="wrong")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(DEV_PASSWORD_LOGIN=True)
    def test_missing_fields_are_rejected(self):
        response = self._post(username="editor")

        self.assertEqual(response.status_code, 400)

    @override_settings(DEV_PASSWORD_LOGIN=True)
    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()

        response = self._post(username="editor", password=PASSWORD)

        self.assertEqual(response.status_code, 400)

    @override_settings(DEV_PASSWORD_LOGIN=True)
    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class ProductionSettingsTests(TestCase):
    def test_dev_login_is_off_in_base_and_production(self):
        import importlib

        for name in ("base", "production"):
            module = importlib.import_module(f"recipe_cms.settings.{name}")
            self.assertFalse(getattr(module, "DEV_PASSWORD_LOGIN", False), name)

    def test_importing_production_does_not_mutate_base_storages(self):
        import importlib
        import sys

        from recipe_cms.settings import base

        sys.modules.pop("recipe_cms.settings.production", None)
        importlib.import_module("recipe_cms.settings.production")
        self.assertNotIn(
            "Manifest", base.STORAGES["staticfiles"]["BACKEND"], base.STORAGES
        )
