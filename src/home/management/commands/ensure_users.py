import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# env prefix -> (superuser?, group name)
ROLES = {
    "ADMIN": (True, None),
    "EDITOR": (False, "Editors"),
    "MODERATOR": (False, "Moderators"),
}


class Command(BaseCommand):
    help = (
        "Create or update the admin (superuser), editor and moderator users from "
        "DJANGO_{ADMIN,EDITOR,MODERATOR}_{USERNAME,PASSWORD,EMAIL}. Roles without "
        "a username and password are skipped. Idempotent, meant for local setups."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        for role, (is_superuser, group_name) in ROLES.items():
            username = os.getenv(f"DJANGO_{role}_USERNAME")
            password = os.getenv(f"DJANGO_{role}_PASSWORD")
            email = os.getenv(f"DJANGO_{role}_EMAIL")
            if not username and not password:
                self.stdout.write(f"Skipped {role.lower()}: no credentials set.")
                continue
            if not username or not password:
                raise CommandError(
                    f"Set both DJANGO_{role}_USERNAME and DJANGO_{role}_PASSWORD."
                )

            user, created = User.objects.get_or_create(
                **{User.USERNAME_FIELD: username}
            )
            if email is not None:
                user.email = email
            user.is_staff = is_superuser
            user.is_superuser = is_superuser
            user.is_active = True
            try:
                validate_password(password, user)
            except ValidationError as error:
                raise CommandError(f"{role.lower()}: " + " ".join(error.messages))
            user.set_password(password)
            user.save()
            if group_name:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)

            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(f"{action} {role.lower()} user '{username}'.")
            )
