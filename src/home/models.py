from django.core.exceptions import ValidationError
from django.db import models
from wagtail.models import Locale, Page


class HomePage(Page):
    description = models.CharField(max_length=255, blank=True, null=True)
    api_fields = ["title", "description"]
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["recipes.RecipePage"]

    def clean(self):
        super().clean()
        # max_count would limit the whole site, but there is one homepage per
        # locale, and the importer and the API rely on that.
        locale_id = self.locale_id or Locale.get_default().pk
        if HomePage.objects.filter(locale_id=locale_id).exclude(pk=self.pk).exists():
            raise ValidationError("There is already a homepage for this language.")
