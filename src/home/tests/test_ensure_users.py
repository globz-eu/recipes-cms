from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

User = get_user_model()

PASSWORD = "a-long-and-uncommon-passphrase"


class EnsureUsersCommandTests(TestCase):
    def _call(self, **env):
        out = StringIO()
        with patch.dict("os.environ", env, clear=True):
            call_command("ensure_users", stdout=out)
        return out.getvalue()

    def test_creates_all_three_users(self):
        self._call(
            DJANGO_ADMIN_USERNAME="admin",
            DJANGO_ADMIN_PASSWORD=PASSWORD,
            DJANGO_EDITOR_USERNAME="editor",
            DJANGO_EDITOR_PASSWORD=PASSWORD,
            DJANGO_MODERATOR_USERNAME="moderator",
            DJANGO_MODERATOR_PASSWORD=PASSWORD,
        )

        admin = User.objects.get(username="admin")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        editor = User.objects.get(username="editor")
        self.assertEqual(
            list(editor.groups.values_list("name", flat=True)), ["Editors"]
        )
        self.assertFalse(editor.is_superuser or editor.is_staff)
        self.assertTrue(editor.check_password(PASSWORD))
        moderator = User.objects.get(username="moderator")
        self.assertEqual(
            list(moderator.groups.values_list("name", flat=True)), ["Moderators"]
        )

    def test_skips_roles_without_credentials(self):
        out = self._call(
            DJANGO_EDITOR_USERNAME="editor", DJANGO_EDITOR_PASSWORD=PASSWORD
        )

        self.assertEqual(User.objects.count(), 1)
        self.assertIn("Skipped", out)

    def test_is_idempotent_and_updates_password(self):
        env = {"DJANGO_EDITOR_USERNAME": "editor", "DJANGO_EDITOR_PASSWORD": PASSWORD}
        self._call(**env)
        env["DJANGO_EDITOR_PASSWORD"] = PASSWORD + "-new"
        self._call(**env)

        self.assertEqual(User.objects.filter(username="editor").count(), 1)
        user = User.objects.get(username="editor")
        self.assertTrue(user.check_password(PASSWORD + "-new"))
        self.assertEqual(user.groups.count(), 1)

    def test_username_without_password_is_an_error(self):
        with self.assertRaises(CommandError):
            self._call(DJANGO_EDITOR_USERNAME="editor")

    def test_weak_password_is_an_error(self):
        with self.assertRaises(CommandError):
            self._call(DJANGO_EDITOR_USERNAME="editor", DJANGO_EDITOR_PASSWORD="123")
