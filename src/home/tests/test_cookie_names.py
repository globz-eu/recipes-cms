import importlib
import os
from unittest import mock

from django.test import SimpleTestCase


class DevCookieNameTests(SimpleTestCase):
    """dev.py reads the cookie names from the environment."""

    def load_dev(self, **env):
        base = {
            k: v
            for k, v in os.environ.items()
            if k not in ("SESSION_COOKIE_NAME", "CSRF_COOKIE_NAME")
        }
        base.update(env)
        from recipe_cms.settings import dev

        with mock.patch.dict(os.environ, base, clear=True):
            return importlib.reload(dev)

    def tearDown(self):
        from recipe_cms.settings import dev

        importlib.reload(dev)

    def test_defaults(self):
        dev = self.load_dev()
        self.assertEqual(dev.SESSION_COOKIE_NAME, "sessionid")
        self.assertEqual(dev.CSRF_COOKIE_NAME, "csrftoken")

    def test_overridden_from_env(self):
        dev = self.load_dev(SESSION_COOKIE_NAME="s_sid", CSRF_COOKIE_NAME="s_csrf")
        self.assertEqual(dev.SESSION_COOKIE_NAME, "s_sid")
        self.assertEqual(dev.CSRF_COOKIE_NAME, "s_csrf")
