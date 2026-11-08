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
