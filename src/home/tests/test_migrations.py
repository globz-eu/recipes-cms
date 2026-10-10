from importlib import import_module

from django.apps import apps
from django.test import TestCase
from wagtail.models import Locale, Page

from home.models import HomePage
from recipes.models import RecipePage

migration = import_module("home.migrations.0004_locales_and_translated_homepages")


class TranslatedHomepagesMigrationTests(TestCase):
    """
    Runs the data migration against content created with the initial
    "en-us" locale, i.e. a database that existed before i18n was enabled.
    """

    def setUp(self):
        migration.remove_translated_homepages(apps, None)
        self.locale = Locale.objects.get(language_code="en")
        self.locale.language_code = "en-us"
        self.locale.save()
        self.homepage = HomePage.objects.get(depth=2)
        self.recipes = [
            self.homepage.add_child(
                instance=RecipePage(
                    title=f"Recipe {i}",
                    slug=f"recipe-{i}",
                    preparation="<p>Cook.</p>",
                    preparation_time=1,
                    cooking_time=1,
                    number_of_people=1,
                )
            )
            for i in range(3)
        ]
        Page.objects.get(depth=1).refresh_from_db()

    def test_normalises_locale_and_keeps_existing_content(self):
        migration.create_translated_homepages(apps, None)

        self.assertFalse(Locale.objects.filter(language_code="en-us").exists())
        en = Locale.objects.get(language_code="en")
        self.assertEqual(en.pk, self.locale.pk)
        for recipe in self.recipes:
            recipe.refresh_from_db()
            self.assertEqual(recipe.locale_id, en.pk)
            self.assertEqual(recipe.get_parent().pk, self.homepage.pk)

    def test_creates_translated_homepages_next_to_the_existing_one(self):
        migration.create_translated_homepages(apps, None)

        root = Page.objects.get(depth=1)
        self.assertEqual(root.numchild, 3)
        self.assertEqual(
            sorted(p.path for p in Page.objects.filter(depth=2)),
            [root.path + "0001", root.path + "0002", root.path + "0003"],
        )
        for code in ["de", "fr"]:
            translated = HomePage.objects.get(locale__language_code=code)
            self.assertEqual(translated.translation_key, self.homepage.translation_key)
            self.assertEqual(translated.get_parent().pk, root.pk)
            self.assertEqual(translated.get_children().count(), 0)

    def test_is_idempotent(self):
        migration.create_translated_homepages(apps, None)
        migration.create_translated_homepages(apps, None)

        self.assertEqual(HomePage.objects.count(), 3)
        self.assertEqual(Page.objects.get(depth=1).numchild, 3)

    def test_reverse_removes_translations_only(self):
        migration.create_translated_homepages(apps, None)
        migration.remove_translated_homepages(apps, None)

        self.assertEqual(list(HomePage.objects.all()), [self.homepage])
        self.assertEqual(Page.objects.get(depth=1).numchild, 1)
        self.assertEqual(RecipePage.objects.count(), 3)
