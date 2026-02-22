"""
Social auth pipeline functions for Auth0 authentication.
"""

from typing import Any, Optional, TYPE_CHECKING
from django.contrib.auth.models import Group
import logging

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)


def add_user_to_editors_group(
    backend: Any,
    user: Optional["AbstractUser"],
    response: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Add newly created users to the Wagtail Editors group.
    This pipeline function runs after user creation in the social auth flow.
    """
    if user and kwargs.get("is_new", False):
        try:
            # Get or create the Editors group (Wagtail creates this by default)
            editors_group, created = Group.objects.get_or_create(name="Editors")

            # Add user to the group
            user.groups.add(editors_group)
            user.save()

            logger.info(f"User {user.username} (ID: {user.pk}) added to Editors group")

        except Exception as e:
            logger.error(f"Error adding user {user.username} to Editors group: {e}")

    return None
