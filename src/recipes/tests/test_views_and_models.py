from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from home.models import HomePage
from recipes.models import RecipePage

User = get_user_model()


class RecipePageStructureTests(WagtailPageTestCase):
    """
    Tests for where RecipePages may live in the page tree.
    """

    def test_can_create_under_homepage(self):
        self.assertCanCreateAt(HomePage, RecipePage)

    def test_cannot_create_under_root(self):
        self.assertCanNotCreateAt(Page, RecipePage)

    def test_cannot_create_under_recipe(self):
        self.assertCanNotCreateAt(RecipePage, RecipePage)

    def test_homepage_allowed_subpages(self):
        self.assertAllowedSubpageTypes(HomePage, {RecipePage})

    def test_recipe_create(self):
        homepage = HomePage.objects.first()
        recipe = RecipePage(
            title="Pancakes",
            ingredients="<ul><li>Flour</li><li>Milk</li><li>Eggs</li></ul>",
            preparation="<p>Mix and fry.</p>",
            preparation_time=10,
            cooking_time=15,
            number_of_people=4,
        )
        homepage.add_child(instance=recipe)
        self.assertTrue(RecipePage.objects.filter(title="Pancakes").exists())
        self.assertEqual(recipe.get_parent().specific, homepage)


class RecipeViewSetTests(APITestCase):
    """
    Tests for RecipeViewSet API endpoints.
    """

    def setUp(self):
        homepage = HomePage.objects.first()
        self.recipe = RecipePage(
            title="Pancakes",
            ingredients="<ul><li>Flour</li></ul>",
            preparation="<p>Mix and fry.</p>",
            preparation_time=10,
            cooking_time=15,
            number_of_people=4,
        )
        homepage.add_child(instance=self.recipe)
        self.draft = RecipePage(title="Draft recipe", live=False)
        homepage.add_child(instance=self.draft)

        self.editor_user = User.objects.create_user(
            username="editor", email="editor@test.com", password="testpass123"
        )
        editors_group, _ = Group.objects.get_or_create(name="Editors")
        self.editor_user.groups.add(editors_group)

        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="testpass123"
        )

    def test_list_recipes_as_editor(self):
        self.client.force_authenticate(user=self.editor_user)
        response = self.client.get(reverse("recipes-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [recipe["title"] for recipe in response.data]
        self.assertIn("Pancakes", titles)
        self.assertNotIn("Draft recipe", titles)

    def test_retrieve_recipe_as_editor(self):
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("recipes-detail", kwargs={"pk": self.recipe.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Pancakes")
        self.assertEqual(response.data["ingredients"], "<ul><li>Flour</li></ul>")
        self.assertEqual(response.data["preparation"], "<p>Mix and fry.</p>")
        self.assertEqual(response.data["preparation_time"], 10)
        self.assertEqual(response.data["cooking_time"], 15)
        self.assertEqual(response.data["number_of_people"], 4)

    def test_rich_text_links_are_expanded(self):
        self.recipe.preparation = (
            f'<p>See <a linktype="page" id="{self.recipe.pk}">this</a>.</p>'
        )
        self.recipe.save()
        self.client.force_authenticate(user=self.editor_user)
        url = reverse("recipes-detail", kwargs={"pk": self.recipe.pk})
        response = self.client.get(url)

        self.assertNotIn("linktype", response.data["preparation"])
        self.assertIn(f'href="{self.recipe.url}"', response.data["preparation"])

    def test_list_recipes_unauthenticated(self):
        response = self.client.get(reverse("recipes-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_recipes_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(reverse("recipes-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_not_allowed(self):
        self.client.force_authenticate(user=self.editor_user)
        response = self.client.post(reverse("recipes-list"), {"title": "New"})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
