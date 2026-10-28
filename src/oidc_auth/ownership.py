"""Lookups enforcing that one email address belongs to one sign-in method."""

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model
from django.db.models import Value
from django.db.models.functions import Lower

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def email_owner(
    email: str, *, exclude: Optional["AbstractUser"] = None
) -> Optional["AbstractUser"]:
    """The first user of any kind with this email (case-insensitive), if any."""
    if not email:
        return None
    # LOWER, like the unique index: iexact uses UPPER, which disagrees for some
    # characters (Kelvin sign) and would let a duplicate through to an IntegrityError.
    users = (
        get_user_model()
        .objects.alias(lowered=Lower("email"))
        .filter(lowered=Lower(Value(email)))
    )
    if exclude is not None:
        users = users.exclude(pk=exclude.pk)
    return users.order_by("pk").first()
