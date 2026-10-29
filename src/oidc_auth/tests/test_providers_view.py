from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

LOCAL = {
    "id": "local",
    "label": "Username and password",
    "login_url": "/admin/login/",
}
AUTH0 = {
    "id": "auth0",
    "label": "Auth0",
    "login_url": "/login/auth0_openidconnect/",
}
ZITADEL = {"id": "zitadel", "label": "Zitadel", "login_url": "/login/zitadel/"}


class AuthProvidersViewTests(TestCase):
    def get(self, **kwargs):
        return self.client.get(reverse("api-auth-providers"), **kwargs)

    def test_url(self):
        self.assertEqual(reverse("api-auth-providers"), "/api/auth/providers/")

    @override_settings(AUTH_PROVIDERS=["local", "auth0"])
    def test_local_and_auth0(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"providers": [LOCAL, AUTH0]})

    @override_settings(AUTH_PROVIDERS=["auth0", "zitadel"])
    def test_social_only_keeps_order(self):
        self.assertEqual(self.get().json(), {"providers": [AUTH0, ZITADEL]})

    @override_settings(AUTH_PROVIDERS=["zitadel"])
    def test_zitadel_only(self):
        self.assertEqual(self.get().json(), {"providers": [ZITADEL]})

    @override_settings(AUTH_PROVIDERS=["zitadel", "local"])
    def test_order_follows_setting_with_local_last(self):
        self.assertEqual(self.get().json(), {"providers": [ZITADEL, LOCAL]})

    def test_anonymous_without_csrf_or_session(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get(reverse("api-auth-providers"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)
