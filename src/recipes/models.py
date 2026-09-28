from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class RecipePage(Page):
    ingredients = RichTextField(blank=True)
    preparation = RichTextField(blank=True)
    preparation_time = models.PositiveIntegerField(
        blank=True, null=True, help_text="Preparation time in minutes"
    )
    cooking_time = models.PositiveIntegerField(
        blank=True, null=True, help_text="Cooking time in minutes"
    )
    number_of_people = models.PositiveSmallIntegerField(blank=True, null=True)

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("number_of_people"),
                FieldPanel("preparation_time"),
                FieldPanel("cooking_time"),
            ],
            heading="Overview",
        ),
        FieldPanel("ingredients"),
        FieldPanel("preparation"),
    ]

    api_fields = [
        "title",
        "ingredients",
        "preparation",
        "preparation_time",
        "cooking_time",
        "number_of_people",
    ]
    parent_page_types = ["home.HomePage"]
    subpage_types: list[str] = []
