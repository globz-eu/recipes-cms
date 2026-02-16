from django.db import models

from wagtail.models import Page


class HomePage(Page):
    description = models.CharField(max_length=255, blank=True, null=True)
    api_fields = ["title", "description"]
    parent_page_types = ["wagtailcore.Page"]
    max_count = 1
