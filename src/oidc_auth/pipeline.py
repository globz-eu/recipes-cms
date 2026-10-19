"""
Social auth pipeline functions for Auth0 authentication.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

ADMIN_ROLE = "admin"


def _get_roles(backend: Any, response: dict[str, Any]) -> set[str]:
    """
    Read the Auth0 roles claim, preferring the validated ID token over the
    userinfo response. A missing or malformed claim means no roles.
    """
    claim = settings.AUTH0_ROLES_CLAIM
    if not claim:
        raise ImproperlyConfigured(
            "AUTH0_ROLES_CLAIM must be set to sync Auth0 roles to Wagtail groups."
        )

    id_token = getattr(backend, "id_token", None)
    if isinstance(id_token, dict) and claim in id_token:
        raw = id_token[claim]
    else:
        raw = response.get(claim)

    if not isinstance(raw, list):
        return set()
    return {role for role in raw if isinstance(role, str)}


def sync_auth0_roles(
    backend: Any,
    user: Optional["AbstractUser"],
    response: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Sync the user's Wagtail groups and superuser status with their Auth0 roles.

    Runs on every login. Only groups listed in ROLE_GROUP_MAP are added or
    removed; the ``admin`` role controls is_superuser and is_staff. A user with
    no roles ends up in no mapped group.
    """
    if user is None:
        return None

    roles = _get_roles(backend, response)
    role_map: dict[str, str] = settings.ROLE_GROUP_MAP
    managed = set(role_map.values())
    wanted = {role_map[role] for role in roles if role in role_map}

    for name in wanted:
        Group.objects.get_or_create(name=name)
    user.groups.remove(*Group.objects.filter(name__in=managed - wanted))
    user.groups.add(*Group.objects.filter(name__in=wanted))

    is_admin = ADMIN_ROLE in roles
    if user.is_superuser != is_admin or user.is_staff != is_admin:
        user.is_superuser = is_admin
        user.is_staff = is_admin
        user.save(update_fields=["is_superuser", "is_staff"])

    logger.info(
        "Synced roles for %s (ID: %s): roles=%s groups=%s",
        user.username,
        user.pk,
        sorted(roles),
        sorted(wanted),
    )
    return None
