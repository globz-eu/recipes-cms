import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Create an admin (superuser) or update an existing one. The password is "
        "read from the DJANGO_ADMIN_PASSWORD environment variable so it never "
        "appears in the process list or shell history."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=os.getenv("DJANGO_ADMIN_USERNAME"),
            help="Username of the admin (default: $DJANGO_ADMIN_USERNAME).",
        )
        parser.add_argument(
            "--email",
            default=os.getenv("DJANGO_ADMIN_EMAIL"),
            help="Email of the admin (default: $DJANGO_ADMIN_EMAIL).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        password = os.getenv("DJANGO_ADMIN_PASSWORD")
        if not username:
            raise CommandError("Pass --username or set DJANGO_ADMIN_USERNAME.")
        if not password:
            raise CommandError("Set DJANGO_ADMIN_PASSWORD.")

        User = get_user_model()
        user, created = User.objects.get_or_create(**{User.USERNAME_FIELD: username})
        if email is not None:
            user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} admin user '{username}'."))
