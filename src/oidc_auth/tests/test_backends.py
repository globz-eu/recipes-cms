from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from social_django.utils import load_strategy

from oidc_auth.backends import ZitadelOpenIdConnect

ORG_SCOPE = "urn:zitadel:iam:org:id:123456"
OWNER_SCOPE = "urn:zitadel:iam:user:resourceowner"


@override_settings(ZITADEL_ROLE_ORG_ID="123456")
class ZitadelOpenIdConnectTests(SimpleTestCase):
    def backend(self):
        return ZitadelOpenIdConnect(load_strategy())

    def test_name(self):
        self.assertEqual(ZitadelOpenIdConnect.name, "zitadel")

    @override_settings(SOCIAL_AUTH_ZITADEL_DOMAIN="example.zitadel.cloud")
    def test_oidc_endpoint_is_built_from_domain(self):
        self.assertEqual(
            self.backend().oidc_endpoint(), "https://example.zitadel.cloud"
        )

    def test_scope_requests_project_roles(self):
        scope = self.backend().get_scope()

        self.assertIn("urn:zitadel:iam:org:project:roles", scope)
        self.assertIn("openid", scope)

    def test_scope_does_not_request_refresh_tokens(self):
        self.assertNotIn("offline_access", self.backend().get_scope())

    def test_scope_requests_the_org_once(self):
        scope = self.backend().get_scope()

        self.assertEqual(scope.count(ORG_SCOPE), 1)
        self.assertIn("profile", scope)
        self.assertIn("email", scope)

    @override_settings(SOCIAL_AUTH_ZITADEL_SCOPE=[ORG_SCOPE])
    def test_org_scope_listed_in_settings_is_not_duplicated(self):
        self.assertEqual(self.backend().get_scope().count(ORG_SCOPE), 1)

    @override_settings(SOCIAL_AUTH_ZITADEL_IGNORE_DEFAULT_SCOPE=True)
    def test_org_scope_is_kept_when_default_scope_is_ignored(self):
        scope = self.backend().get_scope()

        self.assertIn(ORG_SCOPE, scope)
        self.assertNotIn("urn:zitadel:iam:org:project:roles", scope)

    def test_scope_requests_the_resource_owner_once(self):
        self.assertEqual(self.backend().get_scope().count(OWNER_SCOPE), 1)

    @override_settings(SOCIAL_AUTH_ZITADEL_SCOPE=[OWNER_SCOPE])
    def test_resource_owner_scope_listed_in_settings_is_not_duplicated(self):
        self.assertEqual(self.backend().get_scope().count(OWNER_SCOPE), 1)

    @override_settings(SOCIAL_AUTH_ZITADEL_IGNORE_DEFAULT_SCOPE=True)
    def test_resource_owner_scope_is_kept_when_default_scope_is_ignored(self):
        self.assertIn(OWNER_SCOPE, self.backend().get_scope())

    @override_settings(ZITADEL_ROLE_ORG_ID="")
    def test_blank_org_id_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            self.backend().get_scope()
