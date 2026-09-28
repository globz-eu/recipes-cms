from rest_framework import serializers
from wagtail.rich_text import expand_db_html

from .models import RecipePage


class RichTextField(serializers.CharField):
    """Renders Wagtail's internal rich text format (page links, embeds) as HTML."""

    def to_representation(self, value: str) -> str:
        return expand_db_html(value)


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RichTextField(read_only=True)
    preparation = RichTextField(read_only=True)

    class Meta:
        model = RecipePage
        fields = [
            "id",
            "title",
            "slug",
            "ingredients",
            "preparation",
            "preparation_time",
            "cooking_time",
            "number_of_people",
        ]
