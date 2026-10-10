from django.core.exceptions import ValidationError
from django.db import models
from wagtail.models import Page


class HomePage(Page):
    description = models.CharField(max_length=255, blank=True, null=True)
    api_fields = ["title", "description"]
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["recipes.RecipePage"]

    # There is one homepage per locale (max_count would limit the whole site),
    # and the importer and the API rely on that. can_create_at hides "add" and
    # "copy" in the admin, clean() is the backstop for everything else. There
    # is no database constraint, so concurrent creates are not guarded.
    @classmethod
    def can_create_at(cls, parent):
        return (
            super().can_create_at(parent)
            and not cls.objects.filter(locale_id=parent.locale_id).exists()
        )

    def clean(self):
        super().clean()
        locale_id = self.locale_id or self.get_default_locale().pk
        if HomePage.objects.filter(locale_id=locale_id).exclude(pk=self.pk).exists():
            raise ValidationError("There is already a homepage for this language.")
