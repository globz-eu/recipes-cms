from unittest.mock import Mock

from django.contrib.messages import get_messages
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from social_core.exceptions import (
    AuthAlreadyAssociated,
    AuthCanceled,
    AuthForbidden,
    AuthStateMissing,
    AuthTokenError,
)

from oidc_auth.exceptions import AlreadySignedIn, EmailOwnedElsewhere
from oidc_auth.middleware import LOGIN_FAILED_MESSAGE, LoginRefusedMiddleware


@override_settings(SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS=["app.example.com"])
class LoginRefusedMiddlewareTestCase(TestCase):
    def setUp(self):
        self.middleware = LoginRefusedMiddleware(lambda request: HttpResponse())

    def make_request(self, next_url=None):
        request = RequestFactory().get("/auth/complete/zitadel/")
        SessionMiddleware(lambda r: HttpResponse()).process_request(request)
        MessageMiddleware(lambda r: HttpResponse()).process_request(request)
        if next_url is not None:
            request.session["next"] = next_url
        return request

    def refuse(self, request):
        backend = Mock()
        backend.name = "zitadel"
        with self.assertLogs("oidc_auth", level="INFO") as logs:
            response = self.middleware.process_exception(
                request, EmailOwnedElsewhere(backend)
            )
        self.assertIn(
            "INFO:oidc_auth.middleware:Refused zitadel login: email_in_use",
            logs.output,
        )
        self.logs = logs.output
        return response

    def test_safe_next_gets_auth_error_appended(self):
        request = self.make_request("https://app.example.com/login")

        response = self.refuse(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://app.example.com/login?auth_error=email_in_use",
        )

    def test_existing_query_and_fragment_are_kept(self):
        request = self.make_request("/frontend/?locale=de#top")

        response = self.refuse(request)

        self.assertEqual(
            response["Location"], "/frontend/?locale=de&auth_error=email_in_use#top"
        )

    def test_disallowed_next_redirects_to_admin_login(self):
        request = self.make_request("https://evil.example.com/path?token=secret")

        response = self.refuse(request)

        self.assertEqual(response["Location"], reverse("wagtailadmin_login"))
        self.assertIn(
            "WARNING:oidc_auth.redirects:Ignoring disallowed redirect to "
            "https://evil.example.com",
            self.logs,
        )
        self.assertNotIn("secret", "".join(self.logs))

    def test_absent_next_redirects_to_admin_login(self):
        request = self.make_request()

        response = self.refuse(request)

        self.assertEqual(response["Location"], reverse("wagtailadmin_login"))

    def test_next_is_removed_from_session(self):
        request = self.make_request("/frontend/")

        self.refuse(request)

        self.assertNotIn("next", request.session)

    def test_message_is_not_stored_when_redirecting_to_next(self):
        request = self.make_request("/frontend/")

        self.refuse(request)

        self.assertEqual(list(get_messages(request)), [])

    def test_message_is_stored_on_admin_login_fallback(self):
        request = self.make_request()

        self.refuse(request)

        self.assertEqual(
            [m.message for m in get_messages(request)], [EmailOwnedElsewhere.message]
        )

    def handle(self, exception, next_url="/frontend/"):
        request = self.make_request(next_url)
        return request, self.middleware.process_exception(request, exception)

    def test_already_associated_maps_to_already_signed_in(self):
        backend = Mock()
        backend.name = "zitadel"

        request, response = self.handle(AuthAlreadyAssociated(backend))

        self.assertEqual(
            response["Location"], "/frontend/?auth_error=already_signed_in"
        )

    def test_already_associated_message_on_admin_login_fallback(self):
        request, response = self.handle(AuthAlreadyAssociated(Mock()), next_url=None)

        self.assertEqual(response["Location"], reverse("wagtailadmin_login"))
        self.assertEqual(
            [m.message for m in get_messages(request)], [AlreadySignedIn.message]
        )

    def test_canceled_and_forbidden_map_to_login_failed(self):
        for exception in (AuthCanceled(Mock()), AuthForbidden(Mock())):
            with self.subTest(exception=type(exception).__name__):
                request, response = self.handle(exception)

                self.assertEqual(
                    response["Location"], "/frontend/?auth_error=login_failed"
                )

    def test_other_auth_exceptions_map_to_login_failed(self):
        for exception in (AuthStateMissing(Mock()), AuthTokenError(Mock())):
            with self.subTest(exception=type(exception).__name__):
                request, response = self.handle(exception)

                self.assertEqual(
                    response["Location"], "/frontend/?auth_error=login_failed"
                )

    def test_generic_auth_exception_is_logged_as_warning_with_details(self):
        backend = Mock()
        backend.name = "zitadel"
        exception = AuthTokenError(backend, "invalid_client")

        with self.assertLogs("oidc_auth.middleware", level="INFO") as logs:
            self.handle(exception)

        self.assertEqual([r.levelname for r in logs.records], ["WARNING"])
        message = logs.records[0].getMessage()
        self.assertIn("zitadel", message)
        self.assertIn("login_failed", message)
        self.assertIn("AuthTokenError", message)
        self.assertIn("invalid_client", message)
        self.assertIs(logs.records[0].exc_info[1], exception)

    def test_login_failed_message_on_admin_login_fallback(self):
        request, response = self.handle(AuthCanceled(Mock()), next_url=None)

        self.assertEqual(response["Location"], reverse("wagtailadmin_login"))
        self.assertEqual(
            [m.message for m in get_messages(request)], [LOGIN_FAILED_MESSAGE]
        )

    def test_other_exceptions_fall_through(self):
        request = self.make_request()

        self.assertIsNone(self.middleware.process_exception(request, ValueError("x")))

    def test_passes_requests_through(self):
        request = self.make_request()

        self.assertEqual(self.middleware(request).status_code, 200)
