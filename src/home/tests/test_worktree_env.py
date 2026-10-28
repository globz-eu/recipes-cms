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


class EdgeCaseTests(SimpleTestCase):
    def test_replaces_export_prefixed_and_spaced_definitions(self):
        text = "export NGINX_HOST_PORT = 1\n  CSRF_COOKIE_NAME=old\nKEEP=1\n"
        lines = rewrite_env(text, "x", 8082, 5434).splitlines()
        self.assertNotIn("export NGINX_HOST_PORT = 1", lines)
        self.assertNotIn("  CSRF_COOKIE_NAME=old", lines)
        self.assertIn("KEEP=1", lines)
        self.assertEqual(sum(line.startswith("NGINX_HOST_PORT=") for line in lines), 1)
        self.assertEqual(sum(line.startswith("CSRF_COOKIE_NAME=") for line in lines), 1)

    def test_does_not_drop_keys_with_managed_prefix(self):
        out = rewrite_env("NGINX_HOST_PORT_EXTRA=1\n", "x", 8082, 5434)
        self.assertIn("NGINX_HOST_PORT_EXTRA=1", out)

    def test_rerun_keeps_variables_unique(self):
        # Note: the header comment is currently repeated on each run.
        once = rewrite_env(SOURCE, "x", 8081, 5433)
        twice = rewrite_env(once, "x", 8081, 5433).splitlines()
        for key in ("COMPOSE_PROJECT_NAME", "NGINX_HOST_PORT", "CSRF_COOKIE_NAME"):
            self.assertEqual(sum(line.startswith(f"{key}=") for line in twice), 1)

    def test_empty_source(self):
        out = rewrite_env("", "x", 8081, 5433)
        self.assertIn("# Local dev stack", out)
        self.assertIn("NGINX_HOST_PORT=8081", out)

    def test_unusable_project_name_raises(self):
        with self.assertRaises(ValueError):
            rewrite_env("", "///", 8081, 5433)
        with self.assertRaises(ValueError):
            rewrite_env("", "", 1, 1)

    def test_cookie_names_differ_per_project(self):
        a = rewrite_env("", "stack-a", 8081, 5433)
        b = rewrite_env("", "stack-b", 8082, 5434)
        self.assertIn("SESSION_COOKIE_NAME=stack-a_sessionid", a)
        self.assertIn("SESSION_COOKIE_NAME=stack-b_sessionid", b)
