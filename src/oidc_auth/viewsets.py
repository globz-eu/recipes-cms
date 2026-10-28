from wagtail.users.views.users import UserViewSet

from oidc_auth.forms import OwnedEmailUserCreationForm, OwnedEmailUserEditForm


class OwnedEmailUserViewSet(UserViewSet):
    def get_form_class(self, for_update=False):
        if for_update:
            return OwnedEmailUserEditForm
        return OwnedEmailUserCreationForm
