from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

User = get_user_model()

PASSWORD = "a-long-and-uncommon-passphrase"


class EnsureAdminCommandTests(TestCase):
    def _call(self, *args, password=PASSWORD):
        env = {"DJANGO_ADMIN_PASSWORD": password} if password else {}
        out = StringIO()
        with patch.dict("os.environ", env, clear=True):
            call_command("ensure_admin", *args, stdout=out)
        return out.getvalue()

    def test_creates_superuser(self):
        out = self._call("--username", "admin", "--email", "admin@example.com")

        user = User.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "admin@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertIn("Created", out)

    def test_updates_existing_user(self):
        User.objects.create_user(
            username="admin",
            email="old@example.com",
            password="old-password",
            is_active=False,
        )

        out = self._call("--username", "admin", "--email", "new@example.com")

        user = User.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertIn("Updated", out)
        self.assertEqual(User.objects.count(), 1)

    def test_keeps_email_when_not_given(self):
        User.objects.create_user(username="admin", email="keep@example.com")

        self._call("--username", "admin")

        self.assertEqual(User.objects.get(username="admin").email, "keep@example.com")

    def test_reads_username_and_email_from_environment(self):
        env = {
            "DJANGO_ADMIN_USERNAME": "envadmin",
            "DJANGO_ADMIN_EMAIL": "env@example.com",
            "DJANGO_ADMIN_PASSWORD": PASSWORD,
        }
        with patch.dict("os.environ", env, clear=True):
            call_command("ensure_admin", stdout=StringIO())

        user = User.objects.get(username="envadmin")
        self.assertEqual(user.email, "env@example.com")
        self.assertTrue(user.is_superuser)

    def test_requires_username(self):
        with self.assertRaisesMessage(CommandError, "DJANGO_ADMIN_USERNAME"):
            self._call()

    def test_requires_password(self):
        with self.assertRaisesMessage(CommandError, "DJANGO_ADMIN_PASSWORD"):
            self._call("--username", "admin", password=None)

    def test_rejects_weak_password_without_changes(self):
        with self.assertRaises(CommandError):
            self._call("--username", "admin", password="123")

        self.assertFalse(User.objects.filter(username="admin").exists())
