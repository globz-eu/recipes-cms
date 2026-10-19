"""
Social auth pipeline functions shared by all sign-in providers.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured

from oidc_auth.exceptions import EmailNotVerified, EmailOwnedElsewhere
from oidc_auth.ownership import email_owner
from oidc_auth.providers import provider_for_backend, read_claim

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

logger = logging.getLogger(__name__)

ADMIN_ROLE = "admin"


def _is_verified(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() == "true"
    return value is True


def enforce_email_ownership(
    backend: Any,
    details: dict[str, Any],
    response: dict[str, Any],
    user: Optional["AbstractUser"] = None,
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Refuse a social login unless its verified email belongs to no other account.

    One email belongs to one sign-in method: a login is refused (never merged)
    when the email is owned by a local user, by a user linked to another
    provider, or by another user of the same provider. Runs right after
    ``social_user``, so ``user`` is set only for an existing association.
    """
    email = details.get("email") or ""
    if not email or not _is_verified(read_claim(backend, response, "email_verified")):
        raise EmailNotVerified(backend)
    if email_owner(email, exclude=user) is not None:
        raise EmailOwnedElsewhere(backend)
    return None


def sync_roles(
    backend: Any,
    user: Optional["AbstractUser"],
    response: dict[str, Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Sync the user's Wagtail groups and superuser status with the roles from their sign-in provider.

    Runs on every login. Only groups listed in ROLE_GROUP_MAP are added or
    removed; the ``admin`` role controls is_superuser and is_staff. A user with
    no roles ends up in no mapped group.
    """
    if user is None:
        return None

    provider = provider_for_backend(backend.name)
    if provider is None:
        raise ImproperlyConfigured(
            f"No sign-in provider registered for backend {backend.name!r}."
        )

    roles = provider.read_roles(backend, response)
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
        "Synced %s roles for %s (ID: %s): roles=%s groups=%s",
        provider.label,
        user.username,
        user.pk,
        sorted(roles),
        sorted(wanted),
    )
    return None
