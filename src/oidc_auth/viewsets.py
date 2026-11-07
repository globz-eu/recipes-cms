from django import forms
from wagtail.users.views.users import UserViewSet

from oidc_auth.forms import OwnedEmailUserCreationForm, OwnedEmailUserEditForm


class OwnedEmailUserViewSet(UserViewSet):
    def get_form_class(self, for_update: bool = False) -> type[forms.ModelForm]:
        if for_update:
            return OwnedEmailUserEditForm
        return OwnedEmailUserCreationForm
