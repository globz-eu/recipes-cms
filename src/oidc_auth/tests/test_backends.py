from django.test import SimpleTestCase, override_settings
from social_django.utils import load_strategy

from oidc_auth.backends import ZitadelOpenIdConnect


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
