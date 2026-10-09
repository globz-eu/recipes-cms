import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from wagtail.models import Locale

from home.models import HomePage
from recipes.models import RecipeIngredient, RecipePage

User = get_user_model()

URL = reverse("recipes-bulk-upload")


def pancakes(**translations):
    return {"recipes": [{"translations": translations}]}


EN_PANCAKES = {
    "title": "Pancakes",
    "slug": "pancakes",
    "preparation": "<p>Mix and fry.</p>",
    "preparation_time": 10,
    "cooking_time": 15,
    "number_of_people": 4,
    "ingredients": [
        {"quantity": 200, "unit": "g", "name": "Flour"},
        {"quantity": 300, "unit": "ml", "name": "Milk"},
        {"name": "Salt"},
    ],
}
DE_PANCAKES = {
    "title": "Pfannkuchen",
    "ingredients": [{"quantity": 200, "unit": "g", "name": "Mehl"}],
}
FR_PANCAKES = {"title": "Crêpes", "ingredients": [{"name": "Farine"}]}


def create_user(username: str, *groups: str):
    user = User.objects.create_user(
        username=username, email=f"{username}@test.com", password="testpass123"
    )
    user.groups.add(*Group.objects.filter(name__in=groups))
    return user


class LocaleSetUpTests(APITestCase):
    def test_translated_homepages_exist(self):
        en_home = HomePage.objects.get(locale__language_code="en", depth=2)
        for code in ["de", "fr"]:
            homepage = HomePage.objects.get(locale__language_code=code)
            self.assertEqual(homepage.translation_key, en_home.translation_key)
            self.assertEqual(homepage.get_parent().depth, 1)

    def test_default_locale_is_en(self):
        self.assertEqual(Locale.get_default().language_code, "en")


class BulkUploadTests(APITestCase):
    def setUp(self):
        # Editors may use the API but only save drafts; Moderators may also
        # publish (Wagtail's default page permissions)
        self.moderator_user = create_user("moderator", "Editors", "Moderators")
        self.editor_user = create_user("editor", "Editors")
        self.regular_user = create_user("regular")
        self.homepages = {
            code: HomePage.objects.filter(locale__language_code=code)
            .order_by("path")
            .first()
            for code in ["en", "de", "fr"]
        }

    def upload_json(self, payload, user=None):
        self.client.force_authenticate(user=user or self.moderator_user)
        return self.client.post(URL, payload, format="json")

    def upload_file(self, content: bytes):
        self.client.force_authenticate(user=self.moderator_user)
        file = SimpleUploadedFile("recipes.json", content, "application/json")
        return self.client.post(URL, {"file": file}, format="multipart")

    def test_unauthenticated(self):
        response = self.client.post(URL, pancakes(en=EN_PANCAKES), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(URL, pancakes(en=EN_PANCAKES), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_json_body(self):
        response = self.upload_json(pancakes(en=EN_PANCAKES))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["created"]), 1)
        self.assertEqual(response.data["updated"], [])
        self.assertTrue(response.data["created"][0]["live"])
        recipe = RecipePage.objects.get(slug="pancakes")
        self.assertTrue(recipe.live)
        self.assertEqual(recipe.locale.language_code, "en")
        self.assertEqual(recipe.get_parent().specific, self.homepages["en"])
        self.assertEqual(recipe.number_of_people, 4)
        self.assertEqual(
            [str(i) for i in recipe.ingredients.all()],
            ["200 g Flour", "300 ml Milk", "Salt"],
        )
        self.assertIsNotNone(recipe.latest_revision)

    def test_editor_upload_is_draft(self):
        response = self.upload_json(pancakes(en=EN_PANCAKES), user=self.editor_user)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["created"][0]["live"])
        recipe = RecipePage.objects.get(slug="pancakes")
        self.assertFalse(recipe.live)
        self.assertEqual(recipe.get_latest_revision_as_object().number_of_people, 4)

    def test_editor_update_keeps_live_content(self):
        self.upload_json(pancakes(en=EN_PANCAKES))

        response = self.upload_json(
            pancakes(en={**EN_PANCAKES, "number_of_people": 2}),
            user=self.editor_user,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recipe = RecipePage.objects.get(slug="pancakes")
        self.assertTrue(recipe.live)
        self.assertEqual(recipe.number_of_people, 4)
        self.assertTrue(recipe.has_unpublished_changes)
        self.assertEqual(recipe.get_latest_revision_as_object().number_of_people, 2)

    def test_upload_file(self):
        content = json.dumps(pancakes(en=EN_PANCAKES)).encode()
        response = self.upload_file(content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(RecipePage.objects.filter(slug="pancakes").exists())

    def test_upload_top_level_list(self):
        response = self.upload_json([{"translations": {"en": EN_PANCAKES}}])

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_translations_are_linked(self):
        response = self.upload_json(
            pancakes(en=EN_PANCAKES, de=DE_PANCAKES, fr=FR_PANCAKES)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        en = RecipePage.objects.get(slug="pancakes")
        de = RecipePage.objects.get(slug="pfannkuchen")
        fr = RecipePage.objects.get(slug="crêpes")
        self.assertEqual(de.get_parent().specific, self.homepages["de"])
        self.assertEqual(fr.get_parent().specific, self.homepages["fr"])
        self.assertEqual(de.locale.language_code, "de")
        self.assertEqual(
            {p.pk for p in en.get_translations(inclusive=True)},
            {en.pk, de.pk, fr.pk},
        )

    def test_reupload_updates(self):
        self.upload_json(pancakes(en=EN_PANCAKES))
        changed = {
            **EN_PANCAKES,
            "number_of_people": 2,
            "ingredients": [{"quantity": 100, "unit": "g", "name": "Flour"}],
        }
        response = self.upload_json(pancakes(en=changed))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["created"], [])
        self.assertEqual(len(response.data["updated"]), 1)
        recipe = RecipePage.objects.get(slug="pancakes")
        self.assertEqual(RecipePage.objects.filter(slug="pancakes").count(), 1)
        self.assertEqual(recipe.number_of_people, 2)
        self.assertEqual([str(i) for i in recipe.ingredients.all()], ["100 g Flour"])

    def test_add_translation_to_existing_recipe(self):
        recipe = RecipePage(
            title="Pancakes", ingredients=[RecipeIngredient(name="Flour")]
        )
        self.homepages["en"].add_child(instance=recipe)

        response = self.upload_json(pancakes(en=EN_PANCAKES, de=DE_PANCAKES))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        de = RecipePage.objects.get(slug="pfannkuchen")
        self.assertEqual(de.translation_key, recipe.translation_key)

    def test_draft(self):
        response = self.upload_json(pancakes(en={**EN_PANCAKES, "live": False}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(RecipePage.objects.get(slug="pancakes").live)
        titles = [r["title"] for r in self.client.get(reverse("recipes-list")).data]
        self.assertNotIn("Pancakes", titles)

    def assertNothingWritten(self, response):
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(RecipePage.objects.exists())

    def test_unknown_locale(self):
        response = self.upload_json(pancakes(en=EN_PANCAKES, es=DE_PANCAKES))
        self.assertNothingWritten(response)
        self.assertIn("es", str(response.data))

    def test_invalid_json_file(self):
        self.assertNothingWritten(self.upload_file(b"{not json"))

    def test_missing_title(self):
        response = self.upload_json(
            {
                "recipes": [
                    {"translations": {"en": EN_PANCAKES}},
                    {"translations": {"de": {"slug": "ohne-titel"}}},
                ]
            }
        )
        self.assertNothingWritten(response)
        self.assertIn("title", response.data["recipes"][1]["translations"]["de"])

    def test_duplicate_slug_in_upload(self):
        response = self.upload_json(
            {
                "recipes": [
                    {"translations": {"en": EN_PANCAKES}},
                    {"translations": {"en": {**EN_PANCAKES, "title": "Other"}}},
                ]
            }
        )
        self.assertNothingWritten(response)

    def test_empty_upload(self):
        self.assertNothingWritten(self.upload_json({"recipes": []}))

    def test_slugs_of_different_recipes_in_one_group(self):
        self.upload_json(pancakes(en=EN_PANCAKES))
        self.upload_json(pancakes(de=DE_PANCAKES))
        count = RecipePage.objects.count()

        response = self.upload_json(pancakes(en=EN_PANCAKES, de=DE_PANCAKES))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(0, response.data["recipes"])
        self.assertEqual(RecipePage.objects.count(), count)

    def test_existing_translation_with_other_slug(self):
        self.upload_json(pancakes(en=EN_PANCAKES, de=DE_PANCAKES))

        response = self.upload_json(
            pancakes(en=EN_PANCAKES, de={**DE_PANCAKES, "slug": "pfannkuchen-neu"})
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(RecipePage.objects.filter(slug="pfannkuchen-neu").exists())

    def test_error_rolls_back_earlier_groups(self):
        self.upload_json(pancakes(en=EN_PANCAKES, de=DE_PANCAKES))

        response = self.upload_json(
            {
                "recipes": [
                    {"translations": {"en": {"title": "Waffles"}}},
                    {
                        "translations": {
                            "en": EN_PANCAKES,
                            "de": {**DE_PANCAKES, "slug": "pfannkuchen-neu"},
                        }
                    },
                ]
            }
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(list(response.data["recipes"]), [1])
        self.assertFalse(RecipePage.objects.filter(slug="waffles").exists())


class LocaleFilterTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(
            user=create_user("moderator", "Editors", "Moderators")
        )
        self.client.post(URL, pancakes(en=EN_PANCAKES, de=DE_PANCAKES), format="json")

    def test_list_defaults_to_english(self):
        response = self.client.get(reverse("recipes-list"))

        self.assertEqual([r["title"] for r in response.data], ["Pancakes"])
        self.assertEqual(response.data[0]["locale"], "en")

    def test_list_german(self):
        response = self.client.get(reverse("recipes-list"), {"locale": "de"})

        self.assertEqual([r["title"] for r in response.data], ["Pfannkuchen"])
        self.assertEqual(response.data[0]["locale"], "de")

    def test_list_unknown_locale(self):
        response = self.client.get(reverse("recipes-list"), {"locale": "xx"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_any_locale(self):
        de = RecipePage.objects.get(slug="pfannkuchen")
        response = self.client.get(reverse("recipes-detail", kwargs={"pk": de.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["translation_key"], str(de.translation_key))

    def test_home_list_german(self):
        response = self.client.get(reverse("home-list"), {"locale": "de"})

        self.assertEqual(len(response.data), 1)


class ImportRecipesCommandTests(APITestCase):
    def run_command(self, payload) -> str:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            out = StringIO()
            call_command("import_recipes", str(path), stdout=out)
            return out.getvalue()

    def test_import(self):
        output = self.run_command(pancakes(en=EN_PANCAKES, fr=FR_PANCAKES))

        self.assertIn("Created 2 and updated 0", output)
        self.assertEqual(RecipePage.objects.count(), 2)

    def test_invalid(self):
        with self.assertRaises(CommandError):
            self.run_command(pancakes(xx=EN_PANCAKES))
        self.assertFalse(RecipePage.objects.exists())
