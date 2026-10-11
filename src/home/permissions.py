from django.conf import settings
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class IsEditorOrAdmin(permissions.BasePermission):
    """
    Allow admins (superuser or staff) and members of any group that an Auth0 role
    maps to (``settings.AUTH0_ROLE_GROUP_MAP`` values: Editors and Moderators by
    default).

    Authenticated users without permission get a 403 with ``code: "no_access"`` so
    clients can tell them apart from anonymous users.
    """

    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        # User must be authenticated
        if (
            not hasattr(request, "user")
            or not request.user
            or not request.user.is_authenticated
        ):
            return False

        # Allow superusers and staff
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Allow users in any group an Auth0 role maps to
        mapped_groups = set(settings.AUTH0_ROLE_GROUP_MAP.values())
        if request.user.groups.filter(name__in=mapped_groups).exists():
            return True

        raise PermissionDenied(
            detail={
                "detail": "Your account has no access to this content.",
                "code": "no_access",
            }
        )
