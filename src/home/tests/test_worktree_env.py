from django.test import SimpleTestCase

from home.worktree_env import (
    default_postgres_port,
    default_project_name,
    rewrite_env,
)

SOURCE = """SECRET_KEY="abc"
S3_CUSTOM_DOMAIN="localhost:8080/media"
WAGTAILADMIN_BASE_URL="http://localhost:8080"
NGINX_HOST_PORT=9999
# COMPOSE_PROJECT_NAME=ignored comment
POSTGRES_DB=recipes
"""


class RewriteEnvTests(SimpleTestCase):
    def rewrite(self):
        return rewrite_env(SOURCE, "recipes-cms-feat", 8081, 5433)

    def test_drops_derived_urls(self):
        out = self.rewrite()
        self.assertNotIn("S3_CUSTOM_DOMAIN", out)
        self.assertNotIn("WAGTAILADMIN_BASE_URL", out)

    def test_keeps_unrelated_lines_and_comments(self):
        out = self.rewrite()
        self.assertIn('SECRET_KEY="abc"', out)
        self.assertIn("POSTGRES_DB=recipes", out)
        self.assertIn("# COMPOSE_PROJECT_NAME=ignored comment", out)

    def test_sets_managed_variables_once(self):
        lines = self.rewrite().splitlines()
        self.assertEqual(lines.count("NGINX_HOST_PORT=8081"), 1)
        self.assertNotIn("NGINX_HOST_PORT=9999", lines)
        self.assertIn("COMPOSE_PROJECT_NAME=recipes-cms-feat", lines)
        self.assertIn("POSTGRES_HOST_PORT=5433", lines)
        self.assertIn("SESSION_COOKIE_NAME=recipes-cms-feat_sessionid", lines)
        self.assertIn("CSRF_COOKIE_NAME=recipes-cms-feat_csrftoken", lines)

    def test_ends_with_single_newline(self):
        self.assertTrue(self.rewrite().endswith("\n"))
        self.assertFalse(self.rewrite().endswith("\n\n"))

    def test_sanitizes_project_name(self):
        out = rewrite_env("", "Recipes CMS/Feat", 8081, 5433)
        self.assertIn("COMPOSE_PROJECT_NAME=recipes-cms-feat", out)


class DefaultsTests(SimpleTestCase):
    def test_postgres_port_offset(self):
        self.assertEqual(default_postgres_port(8081), 5433)
        self.assertEqual(default_postgres_port(8080), 5432)

    def test_project_name_from_directory(self):
        self.assertEqual(default_project_name("My Feature"), "recipes-cms-my-feature")
