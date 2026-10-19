from django.test import TestCase, override_settings
from django.urls import reverse

PASSWORD_MARKER = 'name="password"'


class WagtailLoginPageTests(TestCase):
    def get(self, **params):
        return self.client.get(reverse("wagtailadmin_login"), params)

    @override_settings(AUTH_PROVIDERS=["local", "auth0", "zitadel"])
    def test_button_per_social_provider_and_password_form(self):
        response = self.get()
        self.assertContains(response, 'href="/login/auth0_openidconnect/"')
        self.assertContains(response, "Sign in with Auth0")
        self.assertContains(response, 'href="/login/zitadel/"')
        self.assertContains(response, "Sign in with Zitadel")
        self.assertContains(response, PASSWORD_MARKER)

    @override_settings(AUTH_PROVIDERS=["zitadel"])
    def test_no_password_form_without_local(self):
        response = self.get()
        self.assertContains(response, 'href="/login/zitadel/"')
        self.assertNotContains(response, "auth0_openidconnect")
        self.assertNotContains(response, PASSWORD_MARKER)

    @override_settings(AUTH_PROVIDERS=["local", "auth0"])
    def test_next_is_forwarded(self):
        response = self.get(next="/admin/pages/")
        self.assertContains(
            response, 'href="/login/auth0_openidconnect/?next=%2Fadmin%2Fpages%2F"'
        )

    @override_settings(AUTH_PROVIDERS=["local"])
    def test_local_only_has_no_provider_buttons(self):
        response = self.get()
        self.assertNotContains(response, "Sign in with")
        self.assertContains(response, PASSWORD_MARKER)


class RestFrameworkLoginPageTests(TestCase):
    def get(self, **params):
        return self.client.get(reverse("rest_framework:login"), params)

    @override_settings(AUTH_PROVIDERS=["local", "auth0", "zitadel"])
    def test_buttons_and_password_form(self):
        response = self.get(next="/api/")
        self.assertContains(
            response, 'href="/login/auth0_openidconnect/?next=%2Fapi%2F"'
        )
        self.assertContains(response, 'href="/login/zitadel/?next=%2Fapi%2F"')
        self.assertContains(response, PASSWORD_MARKER)

    @override_settings(AUTH_PROVIDERS=["auth0"])
    def test_no_password_form_without_local(self):
        response = self.get(next="/api/")
        self.assertContains(response, "/login/auth0_openidconnect/")
        self.assertNotContains(response, PASSWORD_MARKER)
