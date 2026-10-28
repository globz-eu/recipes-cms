from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
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


class SocialUserPasswordTests(TestCase):
    def setUp(self):
        self.social = User.objects.create_user(
            username="social", email="owner@example.com"
        )
        self.social.social_auth.create(provider="zitadel", uid="z-1")
        self.social.set_unusable_password()
        self.social.save()

    def edit_data(self, user, **overrides):
        return creation_data(username=user.username, email=user.email, **overrides)

    def test_edit_form_of_social_user_has_no_password_fields(self):
        form = OwnedEmailUserEditForm(instance=self.social)

        self.assertNotIn("password1", form.fields)
        self.assertNotIn("password2", form.fields)

    def test_posted_password_is_ignored_for_social_user(self):
        form = OwnedEmailUserEditForm(self.edit_data(self.social), instance=self.social)

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.social.refresh_from_db()
        self.assertFalse(self.social.has_usable_password())

    def test_edit_form_of_local_user_keeps_password_fields(self):
        local = User.objects.create_user(
            username="local", email="local@example.com", password=PASSWORD
        )

        form = OwnedEmailUserEditForm(self.edit_data(local), instance=local)

        self.assertIn("password1", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        local.refresh_from_db()
        self.assertTrue(local.check_password(PASSWORD))

    def test_admin_edit_view_does_not_set_password_on_social_user(self):
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=PASSWORD
        )
        self.client.force_login(admin)
        url = reverse("wagtailusers_users:edit", args=[self.social.pk])

        self.assertNotContains(self.client.get(url), 'name="password1"')
        response = self.client.post(url, self.edit_data(self.social))

        self.assertEqual(response.status_code, 302)
        self.social.refresh_from_db()
        self.assertFalse(self.social.has_usable_password())


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


class AccountEmailManagementTests(TestCase):
    def setUp(self):
        self.local = User.objects.create_user(
            username="local", email="local@example.com", password=PASSWORD
        )
        self.local.user_permissions.add(Permission.objects.get(codename="access_admin"))
        self.client.force_login(self.local)

    def test_account_page_does_not_offer_email_change(self):
        response = self.client.get(reverse("wagtailadmin_account"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Name and Email")
        self.assertNotContains(response, 'name="name_email-email"')

    def test_account_page_ignores_posted_email(self):
        social = User.objects.create_user(username="social", email="owner@example.com")
        social.social_auth.create(provider="zitadel", uid="z-1")

        self.client.post(
            reverse("wagtailadmin_account"),
            {
                "name_email-first_name": "A",
                "name_email-last_name": "B",
                "name_email-email": "owner@example.com",
            },
        )

        self.local.refresh_from_db()
        self.assertEqual(self.local.email, "local@example.com")
