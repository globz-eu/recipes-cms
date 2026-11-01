from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from oidc_auth.backends import PermissionsOnlyBackend
from oidc_auth.config import (
    authentication_backends,
    check_provider_settings,
    parse_auth_providers,
)

AUTH0_BACKEND = "social_core.backends.auth0_openidconnect.Auth0OpenIdConnectAuth"
ZITADEL_BACKEND = "oidc_auth.backends.ZitadelOpenIdConnect"
MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
PERMISSIONS_BACKEND = "oidc_auth.backends.PermissionsOnlyBackend"

AUTH0_VALUES = {
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN": "example.auth0.com",
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY": "key",
    "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET": "secret",
    "AUTH0_ROLES_CLAIM": "https://example.com/roles",
}
ZITADEL_VALUES = {
    "SOCIAL_AUTH_ZITADEL_DOMAIN": "example.zitadel.cloud",
    "SOCIAL_AUTH_ZITADEL_KEY": "key",
    "SOCIAL_AUTH_ZITADEL_SECRET": "secret",
    "ZITADEL_ROLE_ORG_ID": "123456789",
}


class ParseAuthProvidersTests(SimpleTestCase):
    def test_default_string(self):
        self.assertEqual(parse_auth_providers("local,auth0"), ["local", "auth0"])

    def test_whitespace_case_and_duplicates(self):
        self.assertEqual(
            parse_auth_providers(" Zitadel , LOCAL,zitadel, local "),
            ["zitadel", "local"],
        )

    def test_unknown_provider_lists_allowed_names(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            parse_auth_providers("local,github")
        message = str(ctx.exception)
        self.assertIn("github", message)
        for name in ("local", "auth0", "zitadel"):
            self.assertIn(name, message)

    def test_blank_is_an_error(self):
        for value in ("", "   ", " , "):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                parse_auth_providers(value)


class AuthenticationBackendsTests(SimpleTestCase):
    def test_local_and_auth0(self):
        self.assertEqual(
            authentication_backends(["local", "auth0"]),
            [AUTH0_BACKEND, MODEL_BACKEND],
        )

    def test_without_local_uses_permissions_only_backend(self):
        self.assertEqual(
            authentication_backends(["auth0", "zitadel"]),
            [AUTH0_BACKEND, ZITADEL_BACKEND, PERMISSIONS_BACKEND],
        )

    def test_social_backends_follow_provider_order(self):
        self.assertEqual(
            authentication_backends(["zitadel", "local"]),
            [ZITADEL_BACKEND, MODEL_BACKEND],
        )


class CheckProviderSettingsTests(SimpleTestCase):
    def test_all_present_passes(self):
        check_provider_settings(
            ["local", "auth0", "zitadel"], {**AUTH0_VALUES, **ZITADEL_VALUES}
        )

    def test_missing_auth0_claim_is_named(self):
        values = {**AUTH0_VALUES}
        del values["AUTH0_ROLES_CLAIM"]
        with self.assertRaises(ImproperlyConfigured) as ctx:
            check_provider_settings(["auth0"], values)
        self.assertIn("AUTH0_ROLES_CLAIM", str(ctx.exception))
        self.assertIn("AUTH_PROVIDERS", str(ctx.exception))

    def test_empty_string_counts_as_missing(self):
        values = {**ZITADEL_VALUES, "SOCIAL_AUTH_ZITADEL_SECRET": ""}
        with self.assertRaises(ImproperlyConfigured) as ctx:
            check_provider_settings(["zitadel"], values)
        self.assertIn("SOCIAL_AUTH_ZITADEL_SECRET", str(ctx.exception))

    def test_none_counts_as_missing(self):
        values = {**ZITADEL_VALUES, "SOCIAL_AUTH_ZITADEL_KEY": None}
        with self.assertRaises(ImproperlyConfigured):
            check_provider_settings(["zitadel"], values)

    def test_whitespace_only_counts_as_missing(self):
        cases = [
            (["zitadel"], ZITADEL_VALUES, "ZITADEL_ROLE_ORG_ID"),
            (["auth0"], AUTH0_VALUES, "SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET"),
        ]
        for providers, base, name in cases:
            for blank in (" ", "\t\n"):
                with self.subTest(name=name, value=blank):
                    with self.assertRaises(ImproperlyConfigured) as ctx:
                        check_provider_settings(providers, {**base, name: blank})
                    self.assertIn(name, str(ctx.exception))

    def test_zitadel_role_org_id_is_required(self):
        values = {**ZITADEL_VALUES}
        del values["ZITADEL_ROLE_ORG_ID"]
        with self.assertRaises(ImproperlyConfigured) as ctx:
            check_provider_settings(["zitadel"], values)
        self.assertIn("ZITADEL_ROLE_ORG_ID", str(ctx.exception))

    def test_auth0_only_needs_no_zitadel_org_id(self):
        check_provider_settings(["local", "auth0"], AUTH0_VALUES)

    def test_disabled_provider_needs_nothing(self):
        check_provider_settings(["local"], {})
        check_provider_settings(["zitadel"], ZITADEL_VALUES)

    def test_multiple_missing_are_all_named(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            check_provider_settings(["auth0", "zitadel"], {})
        message = str(ctx.exception)
        for name in (*AUTH0_VALUES, *ZITADEL_VALUES):
            self.assertIn(name, message)


@override_settings(AUTHENTICATION_BACKENDS=[PERMISSIONS_BACKEND])
class PermissionsOnlyBackendTests(TestCase):
    def test_authenticate_always_returns_none(self):
        get_user_model().objects.create_user("someone", password="pw12345!")
        self.assertIsNone(
            PermissionsOnlyBackend().authenticate(
                None, username="someone", password="pw12345!"
            )
        )

    def test_permissions_still_work(self):
        user = get_user_model().objects.create_user("perm", password="pw12345!")
        user.user_permissions.add(Permission.objects.get(codename="add_user"))
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(user.has_perm("auth.add_user"))
        self.assertFalse(user.has_perm("auth.delete_user"))
