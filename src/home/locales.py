from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from wagtail.models import Locale


def get_requested_locale(request: Request) -> Locale:
    """
    Returns the locale given by the ?locale= query parameter, or the default
    locale (LANGUAGE_CODE) when the parameter is missing.
    """
    language_code = request.query_params.get("locale")
    if not language_code:
        return Locale.get_default()
    try:
        return Locale.objects.get(language_code=language_code)
    except Locale.DoesNotExist:
        raise ValidationError({"locale": [f"Unknown locale '{language_code}'."]})
