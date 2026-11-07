from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class HealthCheckMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path == f"{settings.BASE_PATH}health":
            return HttpResponse("ok")
        return self.get_response(request)
