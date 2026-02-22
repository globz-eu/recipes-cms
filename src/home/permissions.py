from rest_framework import permissions


class IsEditorOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow users who are in the Editors group or are admins.
    """

    def has_permission(self, request, view):
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

        # Allow users in the Editors group
        return request.user.groups.filter(name="Editors").exists()
