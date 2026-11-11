"""social_django's id_key backfill over associations stored before the upgrade."""

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from social_django.models import UserSocialAuth

BEFORE_BACKFILL = ("social_django", "0019_oidc_nonce_lifetime")


class IdKeyBackfillTests(TransactionTestCase):
    serialized_rollback = True

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.addCleanup(self.migrate_to_latest)
        self.executor.migrate([BEFORE_BACKFILL])
        self.executor.loader.build_graph()

    def migrate_to_latest(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.executor.loader.graph.leaf_nodes("social_django"))

    def insert_legacy_rows(self, providers):
        apps = self.executor.loader.project_state([BEFORE_BACKFILL]).apps
        user_model = apps.get_model(settings.AUTH_USER_MODEL)
        social_model = apps.get_model("social_django", "UserSocialAuth")
        for provider in providers:
            user = user_model.objects.create(username=provider)
            social_model.objects.create(
                user=user,
                provider=provider,
                uid=f"{provider}-uid",
                extra_data={"id": f"{provider}-uid"},
            )

    def test_backfills_sub_for_zitadel_and_auth0_rows(self):
        self.insert_legacy_rows(["zitadel", "auth0_openidconnect"])

        self.migrate_to_latest()

        self.assertEqual(
            dict(UserSocialAuth.objects.values_list("provider", "id_key")),
            {"zitadel": "sub", "auth0_openidconnect": "sub"},
        )
