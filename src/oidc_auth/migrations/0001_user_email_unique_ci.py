from django.db import migrations

# One email belongs to one account (one sign-in method). The ownership checks in
# the pipeline, the user forms and the ensure_* commands look before they write;
# this index makes the rule hold under concurrent writes. Case-insensitive, and
# blank emails are left out. Fails if duplicates already exist (see README).
# Assumes the default auth.User table (auth_user).
INDEX = "oidc_auth_user_email_lower_uniq"


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                f'CREATE UNIQUE INDEX "{INDEX}" ON "auth_user" (LOWER("email")) '
                "WHERE \"email\" <> ''"
            ),
            reverse_sql=f'DROP INDEX "{INDEX}"',
        ),
    ]
