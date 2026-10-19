from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from oidc_auth.forms import OwnedEmailUserCreationForm, OwnedEmailUserEditForm

User = get_user_model()

PASSWORD = "a-long-and-uncommon-passphrase"


def creation_data(**overrides):
    data = {
        "username": "newuser",
        "email": "new@example.com",
        "first_name": "New",
        "last_name": "User",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "is_active": "on",
    }
    data.update(overrides)
    return data


class EmailOwnershipFormTests(TestCase):
    def setUp(self):
        self.social = User.objects.create_user(
            username="social", email="Owner@Example.com"
        )
        self.social.social_auth.create(provider="zitadel", uid="z-1")

    def test_creation_rejects_social_owned_email_case_insensitively(self):
        form = OwnedEmailUserCreationForm(creation_data(email="owner@example.COM"))

        self.assertFalse(form.is_valid())
        self.assertIn(
            "This email address belongs to an account that signs in with Zitadel.",
            form.errors["email"],
        )

    def test_unknown_provider_falls_back_to_backend_name(self):
        other = User.objects.create_user(username="o", email="o@example.com")
        other.social_auth.create(provider="mystery", uid="m-1")

        form = OwnedEmailUserCreationForm(creation_data(email="o@example.com"))

        self.assertFalse(form.is_valid())
        self.assertIn("signs in with mystery.", form.errors["email"][0])

    def test_email_of_another_local_user_is_not_rejected_by_this_rule(self):
        User.objects.create_user(username="local", email="local@example.com")

        form = OwnedEmailUserCreationForm(creation_data(email="local@example.com"))

        self.assertNotIn("email", form.errors)

    def test_edit_rejects_social_owned_email_for_other_user(self):
        local = User.objects.create_user(username="local", email="local@example.com")
        data = creation_data(username="local", email="owner@example.com")
        data.pop("password1")
        data.pop("password2")

        form = OwnedEmailUserEditForm(data, instance=local)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_editing_the_social_user_itself_keeps_its_email_valid(self):
        data = creation_data(username="social", email="owner@example.com")
        data.pop("password1")
        data.pop("password2")

        form = OwnedEmailUserEditForm(data, instance=self.social)

        self.assertNotIn("email", form.errors)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class UsersAdminWiringTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=PASSWORD
        )
        self.client.force_login(self.admin)
        social = User.objects.create_user(username="social", email="owner@example.com")
        social.social_auth.create(provider="auth0_openidconnect", uid="a|1")

    def test_add_view_uses_the_custom_form(self):
        response = self.client.post(
            reverse("wagtailusers_users:add"),
            creation_data(email="owner@example.com"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())
        self.assertContains(response, "signs in with Auth0.")

    def test_add_view_still_creates_users_with_free_emails(self):
        response = self.client.post(reverse("wagtailusers_users:add"), creation_data())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())
