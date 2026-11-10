"""Sign-in with associations stored before social-auth-core 6 (no ``id_key``)."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from social_django.models import UserSocialAuth

from oidc_auth.backends import Auth0OpenIdConnect, ZitadelOpenIdConnect
from oidc_auth.config import AUTH0, SOCIAL_BACKENDS
from oidc_auth.tests.login_harness import NEXT, complete_login

User = get_user_model()

EMAIL = "person@example.com"
OWNER_CLAIM = "urn:zitadel:iam:user:resourceowner:id"
ZITADEL_UID = "287654321098765432"
AUTH0_UID = "auth0|65f1c2d3e4f5a6b7c8d9e0f1"
OTHER_UID = "auth0|0000000000000000000000ff"


def zitadel_extra_data(uid):
    """extra_data as social-auth-core 4.9 stored it for a Zitadel login.

    OIDC ``EXTRA_DATA`` stored ``sub`` under ``id``; without ``offline_access``
    there is no refresh token.
    """
    return {
        "auth_time": 1760000000,
        "id_token": "eyJhbGciOiJSUzI1NiJ9.e30.c2ln",
        "refresh_token": None,
        "id": uid,
        "access_token": "access-token",
        "token_type": "Bearer",
    }


def auth0_extra_data(uid):
    """extra_data as social-auth-core 4.9 stored it for an Auth0 login."""
    return {
        **zitadel_extra_data(uid),
        "refresh_token": "refresh-token",
        "picture": "https://example.com/avatar.png",
    }


class LegacyAssociationAssertions(TestCase):
    def legacy_row(self, provider, uid, extra_data):
        """A pre-upgrade association: ``id_key`` blank, as migration 0018 adds it."""
        user = User.objects.create_user("known", email=EMAIL)
        UserSocialAuth.objects.create(
            user=user, provider=provider, uid=uid, id_key="", extra_data=extra_data
        )
        return user

    def assert_signed_in_as(self, response, user):
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("auth_error", response["Location"])
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserSocialAuth.objects.count(), 1)

    def assert_refused(self, response, auth_error):
        self.assertRedirects(
            response,
            f"{NEXT}?auth_error={auth_error}",
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserSocialAuth.objects.count(), 1)


@override_settings(
    AUTHENTICATION_BACKENDS=[
        "oidc_auth.backends.ZitadelOpenIdConnect",
        "django.contrib.auth.backends.ModelBackend",
    ],
    AUTH_PROVIDERS=["local", "zitadel"],
    SOCIAL_AUTH_ZITADEL_DOMAIN="zitadel.example.com",
    SOCIAL_AUTH_ZITADEL_KEY="key",
    SOCIAL_AUTH_ZITADEL_SECRET="secret",
    ZITADEL_ROLE_ORG_ID="org-1",
)
class ZitadelLegacyAssociationTests(LegacyAssociationAssertions):
    def complete(self, uid):
        claims = {
            "sub": uid,
            "email": EMAIL,
            "email_verified": True,
            OWNER_CLAIM: "org-1",
        }
        return complete_login(self.client, ZitadelOpenIdConnect, claims)

    def test_legacy_row_with_matching_id_signs_in_the_same_user(self):
        user = self.legacy_row("zitadel", ZITADEL_UID, zitadel_extra_data(ZITADEL_UID))

        response = self.complete(ZITADEL_UID)

        self.assert_signed_in_as(response, user)
        social = UserSocialAuth.objects.get()
        self.assertEqual((social.uid, social.id_key), (ZITADEL_UID, "sub"))

    def test_legacy_row_with_conflicting_id_is_refused(self):
        self.legacy_row("zitadel", ZITADEL_UID, zitadel_extra_data("other-subject"))

        response = self.complete(ZITADEL_UID)

        self.assert_refused(response, "login_failed")
        self.assertEqual(UserSocialAuth.objects.get().id_key, "")


@override_settings(
    AUTHENTICATION_BACKENDS=[
        SOCIAL_BACKENDS[AUTH0],
        "django.contrib.auth.backends.ModelBackend",
    ],
    AUTH_PROVIDERS=["local", "auth0"],
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="auth0.example.com",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="key",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET="secret",
    AUTH0_ROLES_CLAIM="https://recipes.example.com/roles",
)
class Auth0LegacyAssociationTests(LegacyAssociationAssertions):
    def complete(self, uid):
        claims = {"sub": uid, "email": EMAIL, "email_verified": True}
        return complete_login(self.client, Auth0OpenIdConnect, claims)

    def test_legacy_row_with_matching_id_signs_in_the_same_user(self):
        user = self.legacy_row(
            "auth0_openidconnect", AUTH0_UID, auth0_extra_data(AUTH0_UID)
        )

        response = self.complete(AUTH0_UID)

        self.assert_signed_in_as(response, user)
        social = UserSocialAuth.objects.get()
        self.assertEqual((social.uid, social.id_key), (AUTH0_UID, "sub"))

    def test_legacy_row_with_conflicting_id_is_refused(self):
        self.legacy_row("auth0_openidconnect", AUTH0_UID, auth0_extra_data(OTHER_UID))

        response = self.complete(AUTH0_UID)

        self.assert_refused(response, "login_failed")
        self.assertEqual(UserSocialAuth.objects.get().id_key, "")

    def test_other_identity_with_the_same_email_is_refused(self):
        self.legacy_row("auth0_openidconnect", OTHER_UID, auth0_extra_data(OTHER_UID))

        response = self.complete(AUTH0_UID)

        self.assert_refused(response, "email_in_use")
        self.assertEqual(UserSocialAuth.objects.get().uid, OTHER_UID)
