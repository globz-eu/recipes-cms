from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from oidc_auth.exceptions import EmailNotVerified, EmailOwnedElsewhere
from oidc_auth.ownership import email_owner, social_email_owner
from oidc_auth.pipeline import enforce_email_ownership

User = get_user_model()

EMAIL = "person@example.com"


def make_backend(id_token=None, name="zitadel"):
    backend = Mock()
    backend.name = name
    backend.id_token = id_token
    return backend


class EnforceEmailOwnershipTestCase(TestCase):
    def enforce(self, email=EMAIL, *, verified=True, id_token=None, user=None):
        response = {} if verified is None else {"email_verified": verified}
        return enforce_email_ownership(
            make_backend(id_token),
            {"email": email},
            response,
            user=user,
        )

    def test_new_user_with_unique_verified_email_passes(self):
        self.assertIsNone(self.enforce())

    def test_unverified_email_is_refused(self):
        with self.assertRaises(EmailNotVerified):
            self.enforce(verified=False)

    def test_missing_verified_flag_is_refused(self):
        with self.assertRaises(EmailNotVerified):
            self.enforce(verified=None)

    def test_string_false_is_refused(self):
        with self.assertRaises(EmailNotVerified):
            self.enforce(verified="false")

    def test_string_true_is_accepted(self):
        self.assertIsNone(self.enforce(verified="True"))

    def test_missing_email_is_refused(self):
        with self.assertRaises(EmailNotVerified):
            self.enforce(email="")

    def test_id_token_flag_is_preferred_over_response(self):
        with self.assertRaises(EmailNotVerified):
            self.enforce(verified=True, id_token={"email_verified": False})
        self.assertIsNone(
            self.enforce(verified=False, id_token={"email_verified": True})
        )

    def test_local_user_with_same_email_in_other_case_is_refused(self):
        User.objects.create_user(username="local", email="Person@Example.com")

        with self.assertRaises(EmailOwnedElsewhere):
            self.enforce()

    def test_user_linked_to_other_provider_is_refused(self):
        other = User.objects.create_user(username="auth0user", email=EMAIL)
        other.social_auth.create(provider="auth0_openidconnect", uid="auth0|1")

        with self.assertRaises(EmailOwnedElsewhere):
            self.enforce()

    def test_same_provider_with_different_uid_is_refused(self):
        other = User.objects.create_user(username="zitadeluser", email=EMAIL)
        other.social_auth.create(provider="zitadel", uid="old-uid")

        with self.assertRaises(EmailOwnedElsewhere):
            self.enforce()

    def test_existing_association_with_own_email_passes(self):
        user = User.objects.create_user(username="me", email=EMAIL)
        user.social_auth.create(provider="zitadel", uid="uid")

        self.assertIsNone(self.enforce(user=user))

    def test_existing_association_with_email_of_another_user_is_refused(self):
        user = User.objects.create_user(username="me", email="me@example.com")
        user.social_auth.create(provider="zitadel", uid="uid")
        User.objects.create_user(username="other", email=EMAIL)

        with self.assertRaises(EmailOwnedElsewhere):
            self.enforce(user=user)

    def test_refusals_carry_code_and_message(self):
        User.objects.create_user(username="local", email=EMAIL)

        with self.assertRaises(EmailOwnedElsewhere) as ctx:
            self.enforce()

        self.assertEqual(ctx.exception.code, "email_in_use")
        self.assertEqual(str(ctx.exception), EmailOwnedElsewhere.message)


class OwnershipLookupTestCase(TestCase):
    def test_email_owner_matches_case_insensitively(self):
        user = User.objects.create_user(username="u", email=EMAIL)

        self.assertEqual(email_owner("PERSON@example.com"), user)

    def test_email_owner_excludes_given_user(self):
        user = User.objects.create_user(username="u", email=EMAIL)

        self.assertIsNone(email_owner(EMAIL, exclude=user))

    def test_blank_email_has_no_owner(self):
        User.objects.create_user(username="u", email="")

        self.assertIsNone(email_owner(""))
        self.assertIsNone(social_email_owner(""))

    def test_social_email_owner_ignores_local_users(self):
        User.objects.create_user(username="local", email=EMAIL)
        self.assertIsNone(social_email_owner(EMAIL))

        social = User.objects.create_user(username="social", email="x" + EMAIL)
        social.social_auth.create(provider="zitadel", uid="uid")
        self.assertEqual(social_email_owner("X" + EMAIL), social)
        self.assertIsNone(social_email_owner("x" + EMAIL, exclude=social))
