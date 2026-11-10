"""Social login through the real URL, pipeline and LoginRefusedMiddleware."""

import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape
from django.utils.module_loading import import_string
from social_core.backends.open_id_connect import OpenIdConnectAuth
from social_django.models import UserSocialAuth

from oidc_auth.backends import ZitadelOpenIdConnect
from oidc_auth.config import AUTH0, SOCIAL_BACKENDS
from oidc_auth.exceptions import OrgMismatch
from oidc_auth.tests.login_harness import NEXT, complete_login

User = get_user_model()

EMAIL = "person@example.com"
OWNER_CLAIM = "urn:zitadel:iam:user:resourceowner:id"
AUTH0_DOMAIN = "auth0.example.com"


@override_settings(
    AUTHENTICATION_BACKENDS=[
        SOCIAL_BACKENDS[AUTH0],
        "django.contrib.auth.backends.ModelBackend",
    ],
    AUTH_PROVIDERS=["local", "auth0"],
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=AUTH0_DOMAIN,
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="key",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET="secret",
)
class Auth0LoginStartTests(TestCase):
    def setUp(self):
        OpenIdConnectAuth.get_openid_configuration.invalidate()
        self.addCleanup(OpenIdConnectAuth.get_openid_configuration.invalidate)

    def test_login_redirects_to_the_discovered_authorize_endpoint(self):
        config = {"authorization_endpoint": f"https://{AUTH0_DOMAIN}/authorize"}
        backend_class = import_string(SOCIAL_BACKENDS[AUTH0])
        with patch.object(backend_class, "get_json", return_value=config) as get_json:
            response = self.client.post("/login/auth0_openidconnect/")

        get_json.assert_called_once()
        self.assertEqual(
            get_json.call_args.args,
            (f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",),
        )
        self.assertEqual(response.status_code, 302)
        location = urlsplit(response["Location"])
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            config["authorization_endpoint"],
        )


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
class LoginFlowTestCase(TestCase):
    def complete(self, claims, next_url=NEXT):
        """Complete a Zitadel login of a user of org-1; a ``None`` claim is left out."""
        claims = {
            key: value
            for key, value in {OWNER_CLAIM: "org-1", **claims}.items()
            if value is not None
        }
        return complete_login(self.client, ZitadelOpenIdConnect, claims, next_url)

    def test_login_requests_the_org_and_resource_owner_scopes(self):
        config = {"authorization_endpoint": "https://zitadel.example.com/authorize"}
        with patch.object(ZitadelOpenIdConnect, "oidc_config", lambda self: config):
            response = self.client.post("/login/zitadel/")

        self.assertEqual(response.status_code, 302)
        location = urlsplit(response["Location"])
        self.assertEqual(
            f"{location.scheme}://{location.netloc}{location.path}",
            config["authorization_endpoint"],
        )
        scope = parse_qs(location.query)["scope"][0].split(" ")
        self.assertIn("urn:zitadel:iam:org:id:org-1", scope)
        self.assertIn("urn:zitadel:iam:user:resourceowner", scope)

    def test_login_start_rejects_get(self):
        response = self.client.get("/login/zitadel/")

        self.assertEqual(response.status_code, 405)

    def test_login_start_requires_a_csrf_token(self):
        client = Client(enforce_csrf_checks=True)

        response = client.post("/login/zitadel/", {"next": NEXT})

        self.assertEqual(response.status_code, 403)

    def start_from_login_page(self, page_url, next_url):
        """POST a login page's Zitadel form with its CSRF token, as a browser does."""
        client = Client(enforce_csrf_checks=True)
        page = client.get(page_url, {"next": next_url})
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode()
        )
        self.assertIsNotNone(token)
        config = {"authorization_endpoint": "https://zitadel.example.com/authorize"}
        with patch.object(ZitadelOpenIdConnect, "oidc_config", lambda self: config):
            response = client.post(
                "/login/zitadel/",
                {"csrfmiddlewaretoken": token.group(1), "next": next_url},
            )
        return client, response

    def test_login_page_form_starts_the_login_with_its_csrf_token(self):
        for page_url, next_url in (
            (reverse("wagtailadmin_login"), "/admin/pages/"),
            (reverse("rest_framework:login"), "/api/"),
        ):
            with self.subTest(page=page_url):
                client, response = self.start_from_login_page(page_url, next_url)

                self.assertEqual(response.status_code, 302)
                location = urlsplit(response["Location"])
                self.assertEqual(
                    f"{location.scheme}://{location.netloc}{location.path}",
                    "https://zitadel.example.com/authorize",
                )
                self.assertEqual(client.session["next"], next_url)

    def test_login_start_drops_an_untrusted_next(self):
        client, response = self.start_from_login_page(
            reverse("wagtailadmin_login"), "https://evil.example.org/"
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session["next"], settings.LOGIN_REDIRECT_URL)

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

    def test_user_of_another_org_is_refused_before_creating_anything(self):
        response = self.complete(
            {
                "sub": "uid-1",
                "email": EMAIL,
                "email_verified": True,
                OWNER_CLAIM: "org-2",
            }
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=org_mismatch",
            fetch_redirect_response=False,
        )
        self.assertFalse(User.objects.exists())
        self.assertFalse(UserSocialAuth.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_without_resource_owner_is_refused_before_creating_anything(self):
        response = self.complete(
            {
                "sub": "uid-1",
                "email": EMAIL,
                "email_verified": True,
                OWNER_CLAIM: None,
            }
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=org_mismatch",
            fetch_redirect_response=False,
        )
        self.assertFalse(User.objects.exists())
        self.assertFalse(UserSocialAuth.objects.exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_of_the_org_creates_user_and_logs_in(self):
        response = self.complete(
            {
                "sub": "uid-1",
                "email": EMAIL,
                "email_verified": True,
                OWNER_CLAIM: "org-1",
            }
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("auth_error", response["Location"])
        self.assertTrue(User.objects.filter(email=EMAIL).exists())

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
        # The refusal is social_core's AuthAssociationError (identity_in_use) from
        # social_user, mapped to already_signed_in by the middleware.
        owner = User.objects.create_user("owner", email=EMAIL)
        UserSocialAuth.objects.create(
            user=owner, provider="zitadel", uid="uid-1", id_key="sub"
        )
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

    def test_org_mismatch_without_next_shows_message_on_admin_login(self):
        response = self.complete(
            {
                "sub": "uid-1",
                "email": EMAIL,
                "email_verified": True,
                OWNER_CLAIM: "org-2",
            },
            next_url=None,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/admin/login/"))
        self.assertNotIn("auth_error", response["Location"])
        page = self.client.get(response["Location"])
        self.assertContains(page, escape(OrgMismatch.message))
        self.assertFalse(User.objects.exists())

    def test_existing_linked_user_now_owned_by_another_org_is_refused(self):
        user = User.objects.create_user("known", email=EMAIL)
        UserSocialAuth.objects.create(
            user=user, provider="zitadel", uid="uid-1", id_key="sub"
        )

        response = self.complete(
            {
                "sub": "uid-1",
                "email": EMAIL,
                "email_verified": True,
                OWNER_CLAIM: "org-2",
            }
        )

        self.assertRedirects(
            response,
            f"{NEXT}?auth_error=org_mismatch",
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_org_check_runs_right_after_auth_allowed_before_social_user(self):
        pipeline = list(settings.SOCIAL_AUTH_PIPELINE)
        step = "oidc_auth.pipeline.enforce_zitadel_org"

        self.assertEqual(pipeline.count(step), 1)
        self.assertEqual(
            pipeline.index(step),
            pipeline.index("social_core.pipeline.social_auth.auth_allowed") + 1,
        )
        self.assertLess(
            pipeline.index(step),
            pipeline.index("social_core.pipeline.social_auth.social_user"),
        )

    def test_social_names_runs_right_after_social_details(self):
        pipeline = list(settings.SOCIAL_AUTH_PIPELINE)
        step = "social_core.pipeline.social_auth.social_names"

        self.assertEqual(pipeline.count(step), 1)
        self.assertEqual(
            pipeline.index(step),
            pipeline.index("social_core.pipeline.social_auth.social_details") + 1,
        )
