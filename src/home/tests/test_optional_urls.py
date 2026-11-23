import importlib
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from recipe_cms import urls


class OptionalUrlsTests(TestCase):
    def reload_urls(self, **switches):
        self.enterContext(override_settings(**switches))
        importlib.reload(urls)
        clear_url_caches()

    def tearDown(self):
        super().tearDown()
        self.addCleanup(clear_url_caches)
        self.addCleanup(importlib.reload, urls)

    def test_browsable_api_off_serves_json_to_html_clients(self):
        self.reload_urls(ENABLE_BROWSABLE_API=False)
        # View classes bind their renderers at import, so mirror the setting here.
        self.enterContext(
            mock.patch.object(APIView, "renderer_classes", [JSONRenderer])
        )
        response = self.client.get(
            "/api/", headers={"accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_browsable_api_off_removes_api_auth(self):
        self.reload_urls(ENABLE_BROWSABLE_API=False)
        self.assertEqual(self.client.get("/api-auth/login/").status_code, 404)
        with self.assertRaises(NoReverseMatch):
            reverse("rest_framework:login")
        with self.assertRaises(NoReverseMatch):
            reverse("rest_framework_logout")

    def test_browsable_api_on_keeps_api_auth(self):
        self.reload_urls(ENABLE_BROWSABLE_API=True)
        self.assertEqual(self.client.get("/api-auth/login/").status_code, 200)

    def test_django_admin_off_removes_django_admin_only(self):
        self.reload_urls(ENABLE_DJANGO_ADMIN=False)
        self.assertEqual(self.client.get("/django-admin/").status_code, 404)
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_django_admin_on_serves_django_admin(self):
        self.reload_urls(ENABLE_DJANGO_ADMIN=True)
        self.assertEqual(self.client.get("/django-admin/").status_code, 302)

    def test_both_off_pages_render_without_reverse_errors(self):
        self.reload_urls(
            ENABLE_BROWSABLE_API=False,
            ENABLE_DJANGO_ADMIN=False,
            LOGIN_URL="/admin/login/",
        )
        self.enterContext(
            mock.patch.object(APIView, "renderer_classes", [JSONRenderer])
        )
        for path in ("/admin/login/", "/admin/", "/api/"):
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                self.assertEqual(response.status_code, 200)


class BrowsableApiEnvTests(SimpleTestCase):
    def content_type_for_html_client(self, switch):
        script = (
            "import django; django.setup()\n"
            "from django.test import Client\n"
            "r = Client().get('/api/', headers={'accept': 'text/html,*/*;q=0.8'})\n"
            "print(r.status_code, r['Content-Type'])\n"
        )
        env = {**os.environ, "ENABLE_BROWSABLE_API": switch}
        result = subprocess.run(  # noqa: S603 -- fixed interpreter and script
            [sys.executable, "-c", script],
            env=env,
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_env_switch_off_serves_json_without_patching(self):
        self.assertEqual(
            self.content_type_for_html_client("false"), "200 application/json"
        )

    def test_env_switch_on_serves_html(self):
        self.assertTrue(
            self.content_type_for_html_client("true").startswith("200 text/html")
        )
