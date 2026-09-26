from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import HomePage
from .permissions import IsEditorOrAdmin
from .serializers import HomeSerializer


class HomeViewSet(ReadOnlyModelViewSet):
    serializer_class = HomeSerializer
    queryset = HomePage.objects.all()
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsEditorOrAdmin]


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
