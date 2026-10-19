from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from oidc_auth.pipeline import sync_roles

User = get_user_model()

CLAIM = "https://recipes.example/roles"


@override_settings(
    AUTH0_ROLES_CLAIM=CLAIM,
    ROLE_GROUP_MAP={"editor": "Editors", "moderator": "Moderators"},
)
class SyncRolesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user", email="user@example.com", password="testpass123"
        )

    def sync(self, roles=None, *, response=None, id_token=None, user="default"):
        backend = Mock()
        backend.name = "auth0_openidconnect"
        if id_token is None:
            id_token = {CLAIM: roles} if roles is not None else {}
        backend.id_token = id_token
        return sync_roles(
            backend,
            self.user if user == "default" else user,
            response if response is not None else {},
            is_new=False,
        )

    def group_names(self):
        return set(self.user.groups.values_list("name", flat=True))

    def test_maps_roles_to_groups(self):
        result = self.sync(["editor", "moderator"])

        self.assertEqual(self.group_names(), {"Editors", "Moderators"})
        self.assertIsNone(result)

    def test_creates_missing_groups(self):
        Group.objects.all().delete()

        self.sync(["editor"])

        self.assertEqual(self.group_names(), {"Editors"})

    def test_revoked_role_removes_group(self):
        self.sync(["editor", "moderator"])

        self.sync(["editor"])

        self.assertEqual(self.group_names(), {"Editors"})

    def test_no_roles_means_no_groups(self):
        self.sync(["editor"])

        self.sync([])

        self.assertEqual(self.group_names(), set())

    def test_leaves_unmapped_groups_alone(self):
        other = Group.objects.create(name="Reviewers")
        self.user.groups.add(other)

        self.sync(["editor"])
        self.sync([])

        self.assertEqual(self.group_names(), {"Reviewers"})

    def test_admin_role_sets_superuser_and_staff(self):
        self.sync(["admin"])
        self.user.refresh_from_db()

        self.assertTrue(self.user.is_superuser)
        self.assertTrue(self.user.is_staff)

    def test_missing_admin_role_clears_superuser_and_staff(self):
        self.user.is_superuser = self.user.is_staff = True
        self.user.save()

        self.sync(["editor"])
        self.user.refresh_from_db()

        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)

    def test_admin_role_does_not_add_groups(self):
        self.sync(["admin"])

        self.assertEqual(self.group_names(), set())

    def test_unknown_and_non_string_roles_are_ignored(self):
        self.sync(["editor", "ghost", 7, None, {"x": 1}])

        self.assertEqual(self.group_names(), {"Editors"})

    def test_malformed_claim_means_no_roles(self):
        for claim in ("editor", {"editor": True}, None, 5):
            with self.subTest(claim=claim):
                self.user.groups.add(Group.objects.get_or_create(name="Editors")[0])

                self.sync(id_token={CLAIM: claim})

                self.assertEqual(self.group_names(), set())

    def test_missing_claim_means_no_roles(self):
        self.user.groups.add(Group.objects.get_or_create(name="Editors")[0])

        self.sync(id_token={"email": "user@example.com"})

        self.assertEqual(self.group_names(), set())

    def test_falls_back_to_response_when_id_token_has_no_claim(self):
        self.sync(id_token={}, response={CLAIM: ["editor"]})

        self.assertEqual(self.group_names(), {"Editors"})

    def test_id_token_is_preferred_over_response(self):
        self.sync(id_token={CLAIM: ["moderator"]}, response={CLAIM: ["editor"]})

        self.assertEqual(self.group_names(), {"Moderators"})

    def test_applies_to_existing_users_not_only_new_ones(self):
        backend = Mock()
        backend.name = "auth0_openidconnect"
        backend.id_token = {CLAIM: ["editor"]}

        sync_roles(backend, self.user, {}, is_new=False)

        self.assertEqual(self.group_names(), {"Editors"})

    def test_handles_none_user(self):
        self.assertIsNone(self.sync(["editor"], user=None))

    @override_settings(AUTH0_ROLES_CLAIM="")
    def test_unconfigured_claim_fails_loudly(self):
        with self.assertRaises(ImproperlyConfigured):
            self.sync(["editor"])


ZITADEL_CLAIM = "urn:zitadel:iam:org:project:roles"


@override_settings(ROLE_GROUP_MAP={"editor": "Editors", "moderator": "Moderators"})
class SyncZitadelRolesTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="zuser", email="z@example.com", password="testpass123"
        )

    def sync(self, *, response=None, id_token=None, name="zitadel"):
        backend = Mock()
        backend.name = name
        backend.id_token = id_token if id_token is not None else {}
        return sync_roles(backend, self.user, response or {}, is_new=False)

    def group_names(self):
        return set(self.user.groups.values_list("name", flat=True))

    def test_object_claim_keys_are_roles(self):
        self.sync(
            id_token={ZITADEL_CLAIM: {"editor": {"123": "org.example"}, "ghost": {}}}
        )

        self.assertEqual(self.group_names(), {"Editors"})

    def test_non_object_claims_mean_no_roles(self):
        for claim in (["editor"], "editor", None, 5):
            with self.subTest(claim=claim):
                self.user.groups.add(Group.objects.get_or_create(name="Editors")[0])

                self.sync(id_token={ZITADEL_CLAIM: claim})

                self.assertEqual(self.group_names(), set())

    def test_missing_claim_means_no_roles(self):
        self.user.groups.add(Group.objects.get_or_create(name="Editors")[0])

        self.sync(id_token={})

        self.assertEqual(self.group_names(), set())

    def test_falls_back_to_response(self):
        self.sync(response={ZITADEL_CLAIM: {"moderator": {}}})

        self.assertEqual(self.group_names(), {"Moderators"})

    def test_id_token_is_preferred_over_response(self):
        self.sync(
            id_token={ZITADEL_CLAIM: {"moderator": {}}},
            response={ZITADEL_CLAIM: {"editor": {}}},
        )

        self.assertEqual(self.group_names(), {"Moderators"})

    def test_admin_role_sets_superuser_and_staff(self):
        self.sync(id_token={ZITADEL_CLAIM: {"admin": {}}})
        self.user.refresh_from_db()

        self.assertTrue(self.user.is_superuser)
        self.assertTrue(self.user.is_staff)

    def test_unknown_backend_fails_loudly(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "github"):
            self.sync(name="github")
