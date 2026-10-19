from django.contrib.auth.backends import ModelBackend


class PermissionsOnlyBackend(ModelBackend):
    """Never authenticates; keeps group/user permissions working when password
    login is disabled."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        return None
