from django.db import migrations

DEFAULT_LANGUAGE = "en"
TRANSLATED_LANGUAGES = ["de", "fr"]

# Treebeard materialised path settings used by Wagtail pages
PATH_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PATH_STEPLEN = 4


def _encode_path_step(number):
    step = ""
    while number:
        number, remainder = divmod(number, len(PATH_ALPHABET))
        step = PATH_ALPHABET[remainder] + step
    return step.rjust(PATH_STEPLEN, "0")


def _next_child_path(Page, parent):
    last_child = (
        Page.objects.filter(depth=parent.depth + 1, path__startswith=parent.path)
        .order_by("-path")
        .first()
    )
    number = int(last_child.path[-PATH_STEPLEN:], 36) + 1 if last_child else 1
    return parent.path + _encode_path_step(number)


def create_translated_homepages(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    Page = apps.get_model("wagtailcore.Page")
    HomePage = apps.get_model("home.HomePage")

    source = HomePage.objects.filter(depth=2).order_by("path").first()
    if source is None:
        return

    # The initial locale was derived from LANGUAGE_CODE ("en-us"); normalise it
    default_locale = Locale.objects.filter(language_code=DEFAULT_LANGUAGE).first()
    if default_locale is None:
        default_locale = source.locale
        default_locale.language_code = DEFAULT_LANGUAGE
        default_locale.save()

    root = Page.objects.get(depth=1)
    for language_code in TRANSLATED_LANGUAGES:
        locale, _ = Locale.objects.get_or_create(language_code=language_code)
        if HomePage.objects.filter(
            translation_key=source.translation_key, locale=locale
        ).exists():
            continue
        slug = f"{source.slug}-{language_code}"
        HomePage.objects.create(
            title=source.title,
            draft_title=source.title,
            slug=slug,
            description=source.description,
            content_type_id=source.content_type_id,
            path=_next_child_path(Page, root),
            depth=2,
            numchild=0,
            url_path=f"/{slug}/",
            live=source.live,
            translation_key=source.translation_key,
            locale=locale,
        )
        root.numchild += 1
        root.save(update_fields=["numchild"])


def remove_translated_homepages(apps, schema_editor):
    Locale = apps.get_model("wagtailcore.Locale")
    Page = apps.get_model("wagtailcore.Page")

    root = Page.objects.get(depth=1)
    for locale in Locale.objects.filter(language_code__in=TRANSLATED_LANGUAGES):
        for homepage in Page.objects.filter(depth=2, locale=locale):
            Page.objects.filter(path__startswith=homepage.path).delete()
            root.numchild -= 1
        root.save(update_fields=["numchild"])
        if not Page.objects.filter(locale=locale).exists():
            locale.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0003_homepage_description"),
        ("wagtailcore", "0096_referenceindex_referenceindex_source_object_and_more"),
    ]

    operations = [
        migrations.RunPython(create_translated_homepages, remove_translated_homepages),
    ]
