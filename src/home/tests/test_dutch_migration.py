from importlib import import_module

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from wagtail.models import Locale, Page

from home.models import HomePage
from recipes.models import RecipePage

MIGRATION = "0005_dutch_locale_and_homepage"
migration = import_module(f"home.migrations.{MIGRATION}")


class DutchHomepageMigrationTests(TestCase):
    """
    Runs the data migration functions against a database that has the en, de and
    fr homepages but no Dutch one, using the historical models of the migration
    state like `migrate` does.
    """

    def setUp(self):
        state = MigrationExecutor(connection).loader.project_state(("home", MIGRATION))
        self.apps = state.apps
        migration.remove_dutch_homepage(self.apps, None)
        self.homepage = HomePage.objects.get(locale__language_code="en")
        self.homepage.add_child(
            instance=RecipePage(
                title="Recipe",
                slug="recipe",
                preparation="<p>Cook.</p>",
                preparation_time=1,
                cooking_time=1,
                number_of_people=1,
            )
        )
        self.root = Page.objects.get(depth=1)

    def test_creates_locale_and_homepage_next_to_the_others(self):
        migration.create_dutch_homepage(self.apps, None)

        self.root.refresh_from_db()
        self.assertEqual(self.root.numchild, 4)
        self.assertEqual(
            sorted(p.path for p in Page.objects.filter(depth=2)),
            [self.root.path + f"000{i}" for i in range(1, 5)],
        )
        nl = HomePage.objects.get(locale__language_code="nl")
        self.assertEqual(nl.translation_key, self.homepage.translation_key)
        self.assertEqual(nl.slug, f"{self.homepage.slug}-nl")
        self.assertEqual(nl.url_path, f"/{nl.slug}/")
        self.assertEqual(nl.title, self.homepage.title)
        self.assertEqual(nl.live, self.homepage.live)
        self.assertEqual(nl.get_parent().pk, self.root.pk)
        self.assertEqual(nl.get_children().count(), 0)

    def test_leaves_existing_content_untouched(self):
        migration.create_dutch_homepage(self.apps, None)

        self.assertEqual(
            sorted(Locale.objects.values_list("language_code", flat=True)),
            ["de", "en", "fr", "nl"],
        )
        self.assertEqual(RecipePage.objects.count(), 1)
        self.assertEqual(HomePage.objects.count(), 4)

    def test_is_idempotent(self):
        migration.create_dutch_homepage(self.apps, None)
        migration.create_dutch_homepage(self.apps, None)

        self.assertEqual(HomePage.objects.filter(locale__language_code="nl").count(), 1)
        self.assertEqual(Page.objects.get(depth=1).numchild, 4)

    def test_reverse_removes_dutch_only(self):
        migration.create_dutch_homepage(self.apps, None)
        migration.remove_dutch_homepage(self.apps, None)

        self.assertFalse(Locale.objects.filter(language_code="nl").exists())
        self.assertEqual(HomePage.objects.count(), 3)
        self.assertEqual(Page.objects.get(depth=1).numchild, 3)
        self.assertEqual(RecipePage.objects.count(), 1)

    def test_without_homepage_does_nothing(self):
        RecipePage.objects.all().delete()
        HomePage.objects.all().delete()

        migration.create_dutch_homepage(self.apps, None)

        self.assertFalse(HomePage.objects.exists())
        self.assertFalse(Locale.objects.filter(language_code="nl").exists())
