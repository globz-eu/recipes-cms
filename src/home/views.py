from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import Http404
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from .locales import get_requested_locale
from .models import HomePage
from .permissions import IsEditorOrAdmin
from .serializers import HomeSerializer


class HomeViewSet(ReadOnlyModelViewSet):
    serializer_class = HomeSerializer
    queryset = HomePage.objects.all()
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsEditorOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = queryset.filter(locale=get_requested_locale(self.request))
        return queryset


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfTokenView(APIView):
    """
    Hands the CSRF token to clients that cannot read the csrftoken cookie,
    e.g. the frontend served from a different (same-site) origin.
    The token must be sent back in the X-CSRFToken header on unsafe requests.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrfToken": get_token(request)})


class DevLoginView(APIView):
    """
    Username/password login for the frontend dev server, so local users created
    by ``ensure_users`` can sign in without Auth0. Answers 404 unless
    DEV_PASSWORD_LOGIN is set, which only the dev settings do.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        if not settings.DEV_PASSWORD_LOGIN:
            raise Http404
        username = request.data.get("username")
        password = request.data.get("password")
        user = (
            authenticate(request, username=username, password=password)
            if isinstance(username, str) and isinstance(password, str)
            else None
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response({"username": user.get_username()})
