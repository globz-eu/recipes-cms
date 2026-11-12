from django.test import SimpleTestCase

from oidc_auth.exceptions import EmailNotVerified


class EmailNotVerifiedMessageTests(SimpleTestCase):
    def test_asks_to_verify_or_contact_an_administrator(self):
        self.assertEqual(
            EmailNotVerified.message,
            "Please verify your email address with your provider. "
            "If you didn't get a verification email, ask an administrator to "
            "resend it.",
        )
