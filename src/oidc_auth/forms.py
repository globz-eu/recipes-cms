"""Wagtail user forms that keep each email address on a single account."""

from django import forms
from django.core.exceptions import ValidationError
from wagtail.users.forms import UserCreationForm, UserEditForm

from oidc_auth.ownership import email_owner, has_social_login
from oidc_auth.providers import provider_for_backend


class EmailOwnershipMixin(forms.ModelForm):
    def clean_email(self) -> str:
        email = self.cleaned_data["email"]
        owner = email_owner(email, exclude=self.instance if self.instance.pk else None)
        if owner is None:
            return email
        link = owner.social_auth.first()  # type: ignore[attr-defined]  # reverse accessor added by social_django
        if link is not None:
            provider = provider_for_backend(link.provider)
            name = provider.label if provider else link.provider
            raise ValidationError(
                f"This email address belongs to an account that signs in with {name}."
            )
        raise ValidationError("Another user already has this email address.")


class OwnedEmailUserCreationForm(EmailOwnershipMixin, UserCreationForm):
    pass


class OwnedEmailUserEditForm(EmailOwnershipMixin, UserEditForm):
    @property
    def password_enabled(self) -> bool:
        # Wagtail drops the password fields (and skips them in save()) when this
        # is false. A social user never gets a password: it would be a second
        # sign-in method next to the provider.
        if self.instance.pk and has_social_login(self.instance):
            return False
        return super().password_enabled
