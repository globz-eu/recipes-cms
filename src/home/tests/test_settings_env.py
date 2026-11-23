import importlib
import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from recipe_cms.settings import base
from recipe_cms.settings.base import env_flag, env_list

BROWSABLE = "rest_framework.renderers.BrowsableAPIRenderer"


class EnvListTests(SimpleTestCase):
    def read(self, value=None, **kwargs):
        env = {k: v for k, v in os.environ.items() if k != "TEST_ENV_LIST"}
        if value is not None:
            env["TEST_ENV_LIST"] = value
        with mock.patch.dict(os.environ, env, clear=True):
            return env_list("TEST_ENV_LIST", **kwargs)

    def test_unset_is_empty(self):
        self.assertEqual(self.read(), [])

    def test_empty_is_empty(self):
        self.assertEqual(self.read(""), [])

    def test_splits_and_strips(self):
        self.assertEqual(self.read(" a , b,, ,c "), ["a", "b", "c"])

    def test_default_when_unset_empty_or_blank(self):
        for value in (None, "", " , "):
            self.assertEqual(self.read(value, default=["x"]), ["x"])

    def test_value_wins_over_default(self):
        self.assertEqual(self.read("a", default=["x"]), ["a"])

    def test_default_returned_as_new_list(self):
        default = ["x"]
        result = self.read(default=default)
        self.assertEqual(result, default)
        self.assertIsNot(result, default)


class SecretKeyFallbacksTests(SimpleTestCase):
    def load(self, value=None):
        env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY_FALLBACKS"}
        if value is not None:
            env["SECRET_KEY_FALLBACKS"] = value
        with mock.patch.dict(os.environ, env, clear=True):
            return importlib.reload(base).SECRET_KEY_FALLBACKS

    def tearDown(self):
        importlib.reload(base)

    def test_unset_is_empty(self):
        self.assertEqual(self.load(), [])

    def test_reads_comma_separated_keys(self):
        self.assertEqual(self.load(" old1 ,old2,, "), ["old1", "old2"])


class EnvFlagTests(SimpleTestCase):
    def read(self, value=None, default=True):
        env = {k: v for k, v in os.environ.items() if k != "TEST_ENV_FLAG"}
        if value is not None:
            env["TEST_ENV_FLAG"] = value
        with mock.patch.dict(os.environ, env, clear=True):
            return env_flag("TEST_ENV_FLAG", default=default)

    def test_unset_or_blank_gives_default(self):
        for value in (None, "", "  "):
            self.assertTrue(self.read(value, default=True))
            self.assertFalse(self.read(value, default=False))

    def test_true_and_false_in_any_case(self):
        for value in ("true", "TRUE", " True "):
            self.assertTrue(self.read(value, default=False))
        for value in ("false", "FALSE", " False "):
            self.assertFalse(self.read(value, default=True))

    def test_other_values_raise(self):
        for value in ("1", "yes", "on", "0", "maybe"):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                self.read(value)


class CmsSwitchesTests(SimpleTestCase):
    def load(self, **switches):
        names = ("ENABLE_BROWSABLE_API", "ENABLE_DJANGO_ADMIN")
        env = {k: v for k, v in os.environ.items() if k not in names}
        env.update(switches)
        with mock.patch.dict(os.environ, env, clear=True):
            return importlib.reload(base)

    def tearDown(self):
        importlib.reload(base)

    def test_unset_enables_both(self):
        settings = self.load()
        self.assertTrue(settings.ENABLE_BROWSABLE_API)
        self.assertTrue(settings.ENABLE_DJANGO_ADMIN)
        self.assertIn(BROWSABLE, settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"])
        self.assertEqual(settings.LOGIN_URL, "/api-auth/login/")

    def test_empty_values_enable_both(self):
        settings = self.load(ENABLE_BROWSABLE_API="", ENABLE_DJANGO_ADMIN="")
        self.assertTrue(settings.ENABLE_BROWSABLE_API)
        self.assertTrue(settings.ENABLE_DJANGO_ADMIN)

    def test_browsable_api_off_drops_renderer_and_moves_login(self):
        settings = self.load(ENABLE_BROWSABLE_API="false")
        self.assertFalse(settings.ENABLE_BROWSABLE_API)
        self.assertEqual(
            settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"],
            ["rest_framework.renderers.JSONRenderer"],
        )
        self.assertEqual(settings.LOGIN_URL, "/admin/login/")

    def test_django_admin_off(self):
        settings = self.load(ENABLE_DJANGO_ADMIN="false")
        self.assertFalse(settings.ENABLE_DJANGO_ADMIN)
        self.assertTrue(settings.ENABLE_BROWSABLE_API)

    def test_invalid_value_fails_at_import(self):
        for name in ("ENABLE_BROWSABLE_API", "ENABLE_DJANGO_ADMIN"):
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured):
                self.load(**{name: "yes"})
