"""Social login through the real URL, pipeline and LoginRefusedMiddleware."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from social_django.models import UserSocialAuth

from oidc_auth.backends import ZitadelOpenIdConnect

User = get_user_model()

EMAIL = "person@example.com"
NEXT = "/frontend/"


@override_settings(
    AUTHENTICATION_BACKENDS=[
        "oidc_auth.backends.ZitadelOpenIdConnect",
        "django.contrib.auth.backends.ModelBackend",
    ],
    AUTH_PROVIDERS=["local", "zitadel"],
    SOCIAL_AUTH_ZITADEL_DOMAIN="zitadel.example.com",
    SOCIAL_AUTH_ZITADEL_KEY="key",
    SOCIAL_AUTH_ZITADEL_SECRET="secret",
)
class LoginFlowTestCase(TestCase):
    url = "/complete/zitadel/"

    def complete(self, claims):
        session = self.client.session
        session["next"] = NEXT
        session.save()

        def auth_complete(backend, *args, **kwargs):
            return backend.do_auth("access-token", *args, **kwargs)

        with (
            patch.object(ZitadelOpenIdConnect, "auth_complete", auth_complete),
            patch.object(
                ZitadelOpenIdConnect, "user_data", lambda *a, **k: dict(claims)
            ),
        ):
            return self.client.get(self.url)

    def test_email_owned_by_another_user_is_refused_before_creating_anything(self):
        User.objects.create_user("local", email=EMAIL, password="x")

        response = self.complete(
            {"sub": "uid-1", "email": EMAIL, "email_verified": True}
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=email_in_use",
            fetch_redirect_response=False,
        )
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(UserSocialAuth.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verified_new_email_creates_user_and_logs_in(self):
        response = self.complete(
            {"sub": "uid-1", "email": EMAIL, "email_verified": True}
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("auth_error", response["Location"])
        user = User.objects.get(email=EMAIL)
        self.assertEqual(user.social_auth.get().uid, "uid-1")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))

    def test_unverified_email_is_refused_before_creating_anything(self):
        response = self.complete(
            {"sub": "uid-1", "email": EMAIL, "email_verified": False}
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=email_unverified",
            fetch_redirect_response=False,
        )
        self.assertFalse(User.objects.exists())
        self.assertFalse(UserSocialAuth.objects.exists())

    def test_missing_email_is_refused_before_creating_anything(self):
        response = self.complete({"sub": "uid-1", "email_verified": True})

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=email_missing",
            fetch_redirect_response=False,
        )
        self.assertFalse(User.objects.exists())
        self.assertFalse(UserSocialAuth.objects.exists())

    def test_signed_in_user_linking_a_new_identity_is_refused(self):
        self.client.force_login(User.objects.create_user("other", email="o@x.com"))

        response = self.complete(
            {"sub": "new-uid", "email": "o@x.com", "email_verified": True}
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=already_signed_in",
            fetch_redirect_response=False,
        )
        self.assertFalse(UserSocialAuth.objects.exists())

    def test_identity_owned_by_another_user_is_refused_by_social_user(self):
        # The refusal is social_core's AuthAlreadyAssociated from social_user,
        # mapped to already_signed_in by the middleware (not the ownership step).
        owner = User.objects.create_user("owner", email=EMAIL)
        UserSocialAuth.objects.create(user=owner, provider="zitadel", uid="uid-1")
        self.client.force_login(User.objects.create_user("other", email="o@x.com"))

        response = self.complete(
            {"sub": "uid-1", "email": EMAIL, "email_verified": True}
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=already_signed_in",
            fetch_redirect_response=False,
        )
        self.assertEqual(UserSocialAuth.objects.count(), 1)
