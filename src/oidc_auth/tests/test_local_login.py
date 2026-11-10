"""Local login (`/admin/login/`) follows `next` to ALLOWED_REDIRECT_HOSTS."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from wagtail.admin.views.account import LoginView

from oidc_auth.config import AUTH0, SOCIAL_BACKENDS
from oidc_auth.views import LocalLoginView

User = get_user_model()

PASSWORD = "secret-password"
FRONTEND = "https://static.example.com/frontend/"


@override_settings(
    # AUTHENTICATION_BACKENDS is computed from AUTH_PROVIDERS at import: pin
    # both so password login works whatever the env enables.
    AUTHENTICATION_BACKENDS=["django.contrib.auth.backends.ModelBackend"],
    AUTH_PROVIDERS=["local"],
    ALLOWED_REDIRECT_HOSTS=["static.example.com"],
)
class LocalLoginRedirectTests(TestCase):
    url = "/admin/login/"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password=PASSWORD
        )

    def login(self, next_url, secure=True):
        return self.client.post(
            self.url,
            {"username": "admin", "password": PASSWORD, "next": next_url},
            secure=secure,
        )

    def test_next_on_allowed_host_is_followed(self):
        response = self.login(FRONTEND)
        self.assertRedirects(response, FRONTEND, fetch_redirect_response=False)

    def test_next_on_request_host_is_followed(self):
        response = self.login("/admin/pages/")
        self.assertRedirects(response, "/admin/pages/", fetch_redirect_response=False)

    def test_next_on_other_host_falls_back_to_dashboard(self):
        response = self.login("https://evil.example.com/")
        self.assertRedirects(
            response, reverse("wagtailadmin_home"), fetch_redirect_response=False
        )

    def test_http_next_on_secure_request_falls_back_to_dashboard(self):
        response = self.login("http://static.example.com/frontend/")
        self.assertRedirects(
            response, reverse("wagtailadmin_home"), fetch_redirect_response=False
        )

    def test_http_next_on_plain_request_is_followed(self):
        url = "http://static.example.com/frontend/"
        response = self.login(url, secure=False)
        self.assertRedirects(response, url, fetch_redirect_response=False)

    def test_signed_in_admin_is_sent_to_allowed_next(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"next": FRONTEND}, secure=True)
        self.assertRedirects(response, FRONTEND, fetch_redirect_response=False)

    def test_signed_in_admin_is_not_sent_to_other_host(self):
        self.client.force_login(self.user)
        response = self.client.get(
            self.url, {"next": "https://evil.example.com/"}, secure=True
        )
        self.assertRedirects(
            response, reverse("wagtailadmin_home"), fetch_redirect_response=False
        )

    @override_settings(ALLOWED_REDIRECT_HOSTS=[])
    def test_setting_is_read_per_request(self):
        response = self.login(FRONTEND)
        self.assertRedirects(
            response, reverse("wagtailadmin_home"), fetch_redirect_response=False
        )


@override_settings(
    AUTHENTICATION_BACKENDS=[
        SOCIAL_BACKENDS[AUTH0],
        "django.contrib.auth.backends.ModelBackend",
    ],
    AUTH_PROVIDERS=["local", "auth0"],
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN="auth0.example.com",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="key",
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET="secret",
)
class LocalLoginRouteTests(TestCase):
    def test_admin_login_resolves_to_local_login_view(self):
        match = resolve("/admin/login/")
        self.assertIs(match.func.view_class, LocalLoginView)
        self.assertEqual(match.url_name, "wagtailadmin_login")
        self.assertEqual(reverse("wagtailadmin_login"), "/admin/login/")

    def test_login_page_keeps_template_and_social_buttons(self):
        response = self.client.get("/admin/login/", {"next": "/admin/pages/"})
        self.assertTemplateUsed(response, "wagtailadmin/login.html")
        self.assertContains(
            response, 'href="/login/auth0_openidconnect/?next=%2Fadmin%2Fpages%2F"'
        )
        self.assertContains(response, 'name="password"')


@override_settings(ALLOWED_REDIRECT_HOSTS=["static.example.com"])
class LocalLoginRootCauseTests(TestCase):
    """Issue #35: Django's LoginView allows no host besides the request's."""

    def hosts(self, view_class):
        view = view_class()
        view.setup(RequestFactory().get("/admin/login/", HTTP_HOST="cms.example.com"))
        return view.get_success_url_allowed_hosts()

    def test_stock_wagtail_view_only_allows_request_host(self):
        self.assertEqual(LoginView.success_url_allowed_hosts, set())
        self.assertEqual(self.hosts(LoginView), {"cms.example.com"})

    def test_local_view_adds_allowed_redirect_hosts(self):
        self.assertEqual(
            self.hosts(LocalLoginView), {"cms.example.com", "static.example.com"}
        )

    def test_local_view_accepts_request_argument(self):
        request = RequestFactory().get("/admin/login/", HTTP_HOST="cms.example.com")
        view = LocalLoginView()
        view.setup(request)
        self.assertEqual(
            view.get_success_url_allowed_hosts(request),
            {"cms.example.com", "static.example.com"},
        )
