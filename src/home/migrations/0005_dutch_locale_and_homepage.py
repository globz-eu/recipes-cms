from importlib import import_module

from django.db import migrations

# Migration modules start with a digit, so they cannot be imported normally
_previous = import_module("home.migrations.0004_locales_and_translated_homepages")

LANGUAGE_CODE = "nl"


def create_dutch_homepage(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    Page = apps.get_model("wagtailcore.Page")
    HomePage = apps.get_model("home.HomePage")

    source = HomePage.objects.filter(depth=2).order_by("path").first()
    if source is None:
        return

    locale, _ = Locale.objects.get_or_create(language_code=LANGUAGE_CODE)
    if HomePage.objects.filter(
        translation_key=source.translation_key, locale=locale
    ).exists():
        return

    root = Page.objects.get(depth=1)
    slug = f"{source.slug}-{LANGUAGE_CODE}"
    HomePage.objects.create(
        title=source.title,
        draft_title=source.title,
        slug=slug,
        description=source.description,
        content_type_id=source.content_type_id,
        path=_previous._next_child_path(Page, root),
        depth=2,
        numchild=0,
        url_path=f"/{slug}/",
        live=source.live,
        translation_key=source.translation_key,
        locale=locale,
    )
    root.numchild += 1
    root.save(update_fields=["numchild"])


def remove_dutch_homepage(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    Page = apps.get_model("wagtailcore.Page")

    locale = Locale.objects.filter(language_code=LANGUAGE_CODE).first()
    if locale is None:
        return

    root = Page.objects.get(depth=1)
    for homepage in Page.objects.filter(depth=2, locale=locale):
        Page.objects.filter(path__startswith=homepage.path).delete()
        root.numchild -= 1
    root.save(update_fields=["numchild"])
    if not Page.objects.filter(locale=locale).exists():
        locale.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0004_locales_and_translated_homepages"),
        # The reverse deletes Dutch recipes, so the historical state must know
        # RecipePage and RecipeIngredient for the page delete to cascade to them
        ("recipes", "0002_recipeingredient"),
    ]

    operations = [
        migrations.RunPython(create_dutch_homepage, remove_dutch_homepage),
    ]
