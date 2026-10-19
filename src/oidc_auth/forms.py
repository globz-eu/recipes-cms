"""Wagtail user forms that keep local accounts off social-owned email addresses."""

from django.core.exceptions import ValidationError
from wagtail.users.forms import UserCreationForm, UserEditForm

from oidc_auth.ownership import social_email_owner
from oidc_auth.providers import provider_for_backend


class SocialEmailOwnershipMixin:
    def clean_email(self):
        email = self.cleaned_data["email"]
        owner = social_email_owner(
            email, exclude=self.instance if self.instance.pk else None
        )
        if owner is not None:
            link = owner.social_auth.first()
            provider = provider_for_backend(link.provider)
            name = provider.label if provider else link.provider
            raise ValidationError(
                f"This email address belongs to an account that signs in with {name}."
            )
        return email


class OwnedEmailUserCreationForm(SocialEmailOwnershipMixin, UserCreationForm):
    pass


class OwnedEmailUserEditForm(SocialEmailOwnershipMixin, UserEditForm):
    pass
