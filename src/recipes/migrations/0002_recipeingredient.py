import re
from html import unescape

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations, models


def split_ingredients(html):
    """Turn the old rich text into one entry per list item / paragraph / line."""
    items = re.split(r"</li>|</p>|<br\s*/?>|\n", html)
    for item in items:
        text = unescape(re.sub(r"<[^>]+>", "", item)).strip()
        if text:
            yield text[:255]


def forwards(apps, schema_editor):
    RecipePage = apps.get_model("recipes", "RecipePage")
    RecipeIngredient = apps.get_model("recipes", "RecipeIngredient")
    for page in RecipePage.objects.exclude(old_ingredients=""):
        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(page=page, sort_order=i, name=name)
            for i, name in enumerate(split_ingredients(page.old_ingredients))
        )


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="recipepage",
            old_name="ingredients",
            new_name="old_ingredients",
        ),
        migrations.CreateModel(
            name="RecipeIngredient",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "sort_order",
                    models.IntegerField(blank=True, editable=False, null=True),
                ),
                (
                    "quantity",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=8, null=True
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        blank=True, help_text="e.g. g, ml, tbsp", max_length=50
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "page",
                    modelcluster.fields.ParentalKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingredients",
                        to="recipes.recipepage",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order"],
                "abstract": False,
            },
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="recipepage",
            name="old_ingredients",
        ),
    ]
