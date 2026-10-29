import importlib
import os
from unittest import mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from oidc_auth.redirects import safe_redirect_url


def _env(**env):
    base = {k: v for k, v in os.environ.items() if k != "DEV_FRONTEND_ORIGINS"}
    base.update(env)
    return mock.patch.dict(os.environ, base, clear=True)


class DevFrontendOriginsTests(SimpleTestCase):
    """dev.py trusts the dev server origins from DEV_FRONTEND_ORIGINS."""

    def load_dev(self, **env):
        from recipe_cms.settings import dev

        with _env(**env):
            return importlib.reload(dev)

    def tearDown(self):
        from recipe_cms.settings import dev

        importlib.reload(dev)

    def test_default_when_unset(self):
        dev = self.load_dev()
        self.assertEqual(dev.CSRF_TRUSTED_ORIGINS, ["http://localhost:5173"])
        self.assertEqual(dev.SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS, ["localhost:5173"])

    def test_default_when_empty(self):
        dev = self.load_dev(DEV_FRONTEND_ORIGINS="")
        self.assertEqual(dev.CSRF_TRUSTED_ORIGINS, ["http://localhost:5173"])

    def test_read_from_env(self):
        dev = self.load_dev(
            DEV_FRONTEND_ORIGINS="http://localhost:5174, ,http://localhost:5175 "
        )
        self.assertEqual(
            dev.CSRF_TRUSTED_ORIGINS,
            ["http://localhost:5174", "http://localhost:5175"],
        )
        self.assertEqual(
            dev.SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS,
            ["localhost:5174", "localhost:5175"],
        )


class ProductionIgnoresDevOriginsTests(SimpleTestCase):
    def test_production_reads_only_its_own_variables(self):
        with _env(
            DEV_FRONTEND_ORIGINS="http://localhost:5174",
            CSRF_TRUSTED_ORIGINS="https://app.example.com",
            SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS="",
        ):
            from recipe_cms.settings import production

            production = importlib.reload(production)
        self.assertEqual(production.CSRF_TRUSTED_ORIGINS, ["https://app.example.com"])
        self.assertEqual(production.SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS, [])


@override_settings(
    SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["localhost:5173", "localhost:5174"]
)
class DevServerRedirectTests(TestCase):
    """`next` back to a trusted dev server passes both redirect checks."""

    def request(self):
        # A worktree stack: nginx forwards localhost:8081 as the host.
        return RequestFactory().get("/", HTTP_HOST="localhost:8081")

    def test_logout_and_login_error_redirect(self):
        url = "http://localhost:5174/frontend/"
        self.assertEqual(safe_redirect_url(self.request(), url), url)

    def test_other_dev_server_port_refused(self):
        with self.assertLogs("oidc_auth.redirects", "WARNING"):
            self.assertIsNone(
                safe_redirect_url(self.request(), "http://localhost:5199/frontend/")
            )

    def begin_login(self, next_url):
        # Stop before the provider redirect (it would fetch the OIDC config);
        # social-auth has already stored the sanitized `next` by then.
        with mock.patch(
            "social_core.backends.base.BaseAuth.start", return_value=HttpResponse()
        ):
            self.client.get(
                "/login/auth0_openidconnect/",
                {"next": next_url},
                HTTP_HOST="localhost:8081",
            )
        return self.client.session.get("next")

    @override_settings(AUTH_PROVIDERS=["local", "auth0"])
    def test_social_login_keeps_dev_server_next(self):
        url = "http://localhost:5174/frontend/"
        self.assertEqual(self.begin_login(url), url)

    @override_settings(AUTH_PROVIDERS=["local", "auth0"])
    def test_social_login_drops_untrusted_next(self):
        self.assertNotEqual(
            self.begin_login("http://localhost:5199/frontend/"),
            "http://localhost:5199/frontend/",
        )
