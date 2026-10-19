"""Lookups enforcing that one email address belongs to one sign-in method."""

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def email_owner(
    email: str, *, exclude: Optional["AbstractUser"] = None
) -> Optional["AbstractUser"]:
    """The first user of any kind with this email (case-insensitive), if any."""
    if not email:
        return None
    users = get_user_model().objects.filter(email__iexact=email)
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    return users.order_by("pk").first()


def social_email_owner(
    email: str, *, exclude: Optional["AbstractUser"] = None
) -> Optional["AbstractUser"]:
    """Like email_owner, restricted to users linked to a social sign-in provider."""
    if not email:
        return None
    users = get_user_model().objects.filter(
        email__iexact=email, social_auth__isnull=False
    )
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    return users.distinct().order_by("pk").first()
