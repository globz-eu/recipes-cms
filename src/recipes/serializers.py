import json
from collections import Counter

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from rest_framework import serializers
from wagtail.rich_text import expand_db_html

from .models import RecipeIngredient, RecipePage

MAX_UPLOAD_SIZE = 5 * 1024 * 1024
MAX_RECIPES_PER_UPLOAD = 500


class RichTextField(serializers.CharField):
    """Renders Wagtail's internal rich text format (page links, embeds) as HTML."""

    def to_representation(self, value: str) -> str:
        return expand_db_html(value)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(
        max_digits=8, decimal_places=2, coerce_to_string=False, read_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = ["quantity", "unit", "name"]


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(many=True, read_only=True)
    preparation = RichTextField(read_only=True)
    locale = serializers.CharField(source="locale.language_code", read_only=True)

    class Meta:
        model = RecipePage
        fields = [
            "id",
            "title",
            "slug",
            "locale",
            "translation_key",
            "ingredients",
            "preparation",
            "preparation_time",
            "cooking_time",
            "number_of_people",
        ]


class RecipeIngredientInputSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True, default=None
    )
    unit = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=""
    )
    name = serializers.CharField(max_length=255)


class RecipeTranslationInputSerializer(serializers.Serializer):
    """One language version of a recipe in a bulk upload."""

    title = serializers.CharField(max_length=255)
    slug = serializers.SlugField(
        max_length=255, allow_unicode=True, required=False, allow_blank=True
    )
    ingredients = RecipeIngredientInputSerializer(
        many=True, required=False, default=list
    )
    preparation = serializers.CharField(required=False, allow_blank=True, default="")
    preparation_time = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, default=None
    )
    cooking_time = serializers.IntegerField(
        min_value=0, required=False, allow_null=True, default=None
    )
    number_of_people = serializers.IntegerField(
        min_value=0, max_value=32767, required=False, allow_null=True, default=None
    )
    live = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("slug"):
            attrs["slug"] = slugify(attrs["title"], allow_unicode=True)
            if not attrs["slug"]:
                raise serializers.ValidationError(
                    {"slug": ["Could not derive a slug from the title; pass one."]}
                )
        return attrs


class RecipeGroupInputSerializer(serializers.Serializer):
    """All language versions of one recipe, keyed by language code."""

    translations = serializers.DictField(child=RecipeTranslationInputSerializer())

    def validate_translations(self, value: dict) -> dict:
        if not value:
            raise serializers.ValidationError("At least one translation is required.")
        language_codes = {code for code, _ in settings.WAGTAIL_CONTENT_LANGUAGES}
        unknown = sorted(set(value) - language_codes)
        if unknown:
            raise serializers.ValidationError(
                f"Unknown locale(s): {', '.join(unknown)}. "
                f"Supported: {', '.join(sorted(language_codes))}."
            )
        return value


class BulkUploadSerializer(serializers.Serializer):
    recipes = serializers.ListField(
        child=RecipeGroupInputSerializer(),
        allow_empty=False,
        max_length=MAX_RECIPES_PER_UPLOAD,
    )

    def validate_recipes(self, value: list) -> list:
        slugs = Counter(
            (code, translation["slug"])
            for group in value
            for code, translation in group["translations"].items()
        )
        duplicates = sorted(key for key, count in slugs.items() if count > 1)
        if duplicates:
            raise serializers.ValidationError(
                "Duplicate slugs in upload: "
                + ", ".join(f"{slug} ({code})" for code, slug in duplicates)
            )
        return value


def load_json_upload(file: UploadedFile) -> object:
    """Decodes an uploaded JSON file, raising a ValidationError for bad files."""
    if file.size > MAX_UPLOAD_SIZE:
        raise serializers.ValidationError(
            {"file": [f"File too large; the maximum is {MAX_UPLOAD_SIZE} bytes."]}
        )
    try:
        return json.loads(file.read().decode("utf-8"))
    except UnicodeDecodeError:
        raise serializers.ValidationError({"file": ["File must be UTF-8 encoded."]})
    except json.JSONDecodeError as error:
        raise serializers.ValidationError({"file": [f"Invalid JSON: {error}"]})
