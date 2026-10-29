import os
from unittest import mock

from django.test import SimpleTestCase

from recipe_cms.settings.base import env_list


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
