from django.conf import settings
from django.core.files.storage import default_storage, storages
from django.test import SimpleTestCase, TestCase


class TestSettingsTestCase(SimpleTestCase):
    def test_settings_module_is_test_settings(self):
        self.assertEqual(settings.SETTINGS_MODULE, "recipe_cms.settings.test")

    def test_database_is_sqlite_unless_postgres_is_configured(self):
        engine = settings.DATABASES["default"]["ENGINE"]

        self.assertIn(
            engine, {"django.db.backends.sqlite3", "django.db.backends.postgresql"}
        )

    def test_default_storage_is_in_memory(self):
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.InMemoryStorage",
        )
        self.assertEqual(type(default_storage._wrapped).__name__, "InMemoryStorage")
        self.assertEqual(type(storages["default"]).__name__, "InMemoryStorage")


class TestDatabaseVendorTestCase(TestCase):
    def test_vendor_matches_configured_engine(self):
        from django.db import connection

        if settings.DATABASES["default"]["ENGINE"].endswith("sqlite3"):
            self.assertEqual(connection.vendor, "sqlite")
        else:
            self.assertEqual(connection.vendor, "postgresql")


class TestSettingsModuleTestCase(SimpleTestCase):
    """Import recipe_cms.settings.test in a clean process with chosen env."""

    def load(self, **env):
        import json
        import os
        import subprocess
        import sys

        base = {
            k: v
            for k, v in os.environ.items()
            if k not in {"POSTGRES_HOST", "SECRET_KEY", "AUTH_PROVIDERS"}
            and not k.startswith("SOCIAL_AUTH_")
            and k != "DJANGO_SETTINGS_MODULE"
        }
        src = __import__("pathlib").Path(__file__).resolve().parents[2]
        code = (
            "import sys, json; sys.path.insert(0, {src!r});"
            "from recipe_cms.settings import test as s;"
            "print(json.dumps({'db': s.DATABASES['default'],"
            " 'key': s.SECRET_KEY, 'hashers': s.PASSWORD_HASHERS,"
            " 'storage': s.STORAGES['default']['BACKEND'],"
            " 'static': 'staticfiles' in s.STORAGES}))"
        ).replace("{src!r}", repr(str(src)))
        root = src
        out = subprocess.run(
            [sys.executable, "-c", code],
            env={**base, **env},
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_needs_no_environment_and_uses_sqlite_in_memory(self):
        result = self.load()

        self.assertEqual(result["db"]["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(result["db"]["NAME"], ":memory:")
        self.assertEqual(result["key"], "test-only-secret-key")
        self.assertTrue(result["static"])

    def test_fast_password_hasher(self):
        self.assertEqual(
            self.load()["hashers"], ["django.contrib.auth.hashers.MD5PasswordHasher"]
        )

    def test_postgres_host_keeps_the_postgres_database(self):
        result = self.load(POSTGRES_HOST="db")

        self.assertEqual(result["db"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(result["db"]["HOST"], "db")

    def test_existing_secret_key_wins(self):
        self.assertEqual(self.load(SECRET_KEY="given")["key"], "given")

    def test_storage_is_in_memory(self):
        self.assertEqual(
            self.load()["storage"], "django.core.files.storage.InMemoryStorage"
        )
