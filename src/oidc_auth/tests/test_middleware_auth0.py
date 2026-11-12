from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from social_core.exceptions import (
    AuthAssociationError,
    AuthCanceled,
    AuthCredentialError,
    AuthSessionError,
)

from oidc_auth.exceptions import EmailNotVerified
from oidc_auth.middleware import LOGIN_FAILED_MESSAGE, LoginRefusedMiddleware
from oidc_auth.tests.login_harness import auth0_logout_location

AUTH0_DOMAIN = "auth0.example.com"
COMPLETE_PATH = "/complete/auth0_openidconnect/"
ADMIN_HOME = "http://testserver/admin/"


def named_backend(name):
    backend = Mock()
    backend.name = name
    return backend


@override_settings(
    ALLOWED_REDIRECT_HOSTS=["app.example.com"],
    AUTH_PROVIDERS=["local", "auth0", "zitadel"],
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=AUTH0_DOMAIN,
    SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY="key",
)
class Auth0RefusalLogoutTestCase(TestCase):
    def setUp(self):
        self.middleware = LoginRefusedMiddleware(lambda request: HttpResponse())

    def make_request(self, next_url=None, path=COMPLETE_PATH):
        request = RequestFactory().get(path)
        SessionMiddleware(lambda r: HttpResponse()).process_request(request)
        MessageMiddleware(lambda r: HttpResponse()).process_request(request)
        if next_url is not None:
            request.session["next"] = next_url
        return request

    def handle(self, exception, next_url="/frontend/", request=None):
        request = request or self.make_request(next_url)
        with self.assertLogs("oidc_auth", level="INFO") as logs:
            response = self.middleware.process_exception(request, exception)
        self.logs = logs.output
        return request, response

    def auth0_refusal(self):
        return EmailNotVerified(named_backend("auth0_openidconnect"))

    def return_to(self, response):
        location = urlsplit(response["Location"])
        self.assertEqual(
            (location.scheme, location.netloc, location.path),
            ("https", AUTH0_DOMAIN, "/v2/logout"),
        )
        params = parse_qs(location.query)
        self.assertEqual(params["client_id"], ["key"])
        return params["returnTo"][0]

    def stored_messages(self, request):
        return [m.message for m in get_messages(request)]

    def test_every_auth0_failure_logs_out_of_auth0(self):
        backend = named_backend("auth0_openidconnect")
        for exception, code in (
            (EmailNotVerified(backend), "email_unverified"),
            (AuthAssociationError(backend), "already_signed_in"),
            (AuthCanceled(backend), "login_failed"),
            (AuthSessionError(backend), "login_failed"),
            (AuthCredentialError(backend), "login_failed"),
        ):
            with self.subTest(exception=type(exception).__name__):
                _, response = self.handle(exception)

                self.assertEqual(
                    response["Location"],
                    auth0_logout_location(
                        AUTH0_DOMAIN, f"http://testserver/frontend/?auth_error={code}"
                    ),
                )

    def test_frontend_return_to_keeps_the_query_and_adds_auth_error(self):
        request, response = self.handle(
            self.auth0_refusal(), next_url="/frontend/?locale=de"
        )

        self.assertEqual(
            self.return_to(response),
            "http://testserver/frontend/?locale=de&auth_error=email_unverified",
        )
        self.assertEqual(self.stored_messages(request), [])

    def test_frontend_on_an_allowed_host_stays_on_that_host(self):
        _, response = self.handle(
            self.auth0_refusal(), next_url="https://app.example.com/frontend/"
        )

        self.assertEqual(
            self.return_to(response),
            "https://app.example.com/frontend/?auth_error=email_unverified",
        )

    def test_other_targets_return_to_the_admin_with_the_message(self):
        for next_url in (
            "/admin/pages/",
            reverse("wagtailadmin_login"),
            "https://evil.example.com/frontend/",
            None,
        ):
            with self.subTest(next_url=next_url):
                request, response = self.handle(self.auth0_refusal(), next_url)

                self.assertEqual(self.return_to(response), ADMIN_HOME)
                self.assertEqual(
                    self.stored_messages(request), [EmailNotVerified.message]
                )

    def test_generic_failure_message_on_the_admin_return(self):
        request, response = self.handle(
            AuthCanceled(named_backend("auth0_openidconnect")), next_url=None
        )

        self.assertEqual(self.return_to(response), ADMIN_HOME)
        self.assertEqual(self.stored_messages(request), [LOGIN_FAILED_MESSAGE])

    def test_backend_is_detected_from_the_request(self):
        request = self.make_request("/frontend/")
        request.backend = named_backend("auth0_openidconnect")

        _, response = self.handle(AuthCanceled(Mock()), request=request)

        self.assertIn("Failed auth0_openidconnect login", self.logs[0])
        self.assertEqual(
            self.return_to(response),
            "http://testserver/frontend/?auth_error=login_failed",
        )

    def test_backend_is_detected_from_the_complete_url(self):
        request = self.make_request("/frontend/")
        request.resolver_match = resolve(COMPLETE_PATH)

        _, response = self.handle(AuthCanceled(Mock()), request=request)

        self.assertIn("Failed auth0_openidconnect login", self.logs[0])
        self.assertEqual(
            self.return_to(response),
            "http://testserver/frontend/?auth_error=login_failed",
        )

    def test_other_or_unknown_backends_redirect_as_before(self):
        for backend in (named_backend("zitadel"), Mock()):
            with self.subTest(backend=backend.name):
                _, response = self.handle(AuthCanceled(backend))

                self.assertEqual(
                    response["Location"], "/frontend/?auth_error=login_failed"
                )

    def test_unknown_backend_is_logged_as_unknown(self):
        self.handle(AuthCanceled(Mock()))

        self.assertIn("Failed unknown login", self.logs[0])

    @override_settings(AUTH_PROVIDERS=["local", "zitadel"])
    def test_auth0_failure_redirects_as_before_when_auth0_is_disabled(self):
        request, response = self.handle(self.auth0_refusal(), next_url=None)

        self.assertEqual(response["Location"], reverse("wagtailadmin_login"))
        self.assertEqual(self.stored_messages(request), [EmailNotVerified.message])
