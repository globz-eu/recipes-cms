from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page


class RecipePage(Page):
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
        InlinePanel("ingredients", label="Ingredients"),
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


class RecipeIngredient(Orderable):
    page = ParentalKey(RecipePage, on_delete=models.CASCADE, related_name="ingredients")
    quantity = models.DecimalField(
        max_digits=8, decimal_places=2, blank=True, null=True
    )
    unit = models.CharField(max_length=50, blank=True, help_text="e.g. g, ml, tbsp")
    name = models.CharField(max_length=255)

    panels = [
        FieldPanel("quantity"),
        FieldPanel("unit"),
        FieldPanel("name"),
    ]
    api_fields = ["quantity", "unit", "name"]

    def __str__(self) -> str:
        quantity = f"{self.quantity.normalize():f}" if self.quantity else ""
        return " ".join(part for part in (quantity, self.unit, self.name) if part)
