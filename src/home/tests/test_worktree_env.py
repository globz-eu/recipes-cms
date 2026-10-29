from django.test import SimpleTestCase

from home.worktree_env import (
    HEADER,
    check_ports,
    default_dev_server_port,
    default_postgres_port,
    default_project_name,
    rewrite_env,
)

SOURCE = """SECRET_KEY="abc"
S3_CUSTOM_DOMAIN="localhost:8080/media"
WAGTAILADMIN_BASE_URL="http://localhost:8080"
NGINX_HOST_PORT=9999
DEV_FRONTEND_ORIGINS=http://localhost:9999
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
        self.assertNotIn("DEV_FRONTEND_ORIGINS=http://localhost:9999", lines)

    def test_ends_with_single_newline(self):
        self.assertTrue(self.rewrite().endswith("\n"))
        self.assertFalse(self.rewrite().endswith("\n\n"))

    def test_sanitizes_project_name(self):
        out = rewrite_env("", "Recipes CMS/Feat", 8081, 5433)
        self.assertIn("COMPOSE_PROJECT_NAME=recipes-cms-feat", out)


class DevFrontendOriginsTests(SimpleTestCase):
    def origins(self, *args):
        lines = rewrite_env(SOURCE, "x", 8081, 5433, *args).splitlines()
        found = [line for line in lines if line.startswith("DEV_FRONTEND_ORIGINS=")]
        self.assertEqual(len(found), 1)
        return found[0].removeprefix("DEV_FRONTEND_ORIGINS=")

    def test_default_pairs_with_nginx_port(self):
        self.assertEqual(self.origins(), "http://localhost:5173,http://localhost:5174")

    def test_explicit_dev_server_port(self):
        self.assertEqual(
            self.origins(5180), "http://localhost:5173,http://localhost:5180"
        )

    def test_main_dev_server_port_listed_once(self):
        self.assertEqual(self.origins(5173), "http://localhost:5173")


class CheckPortsTests(SimpleTestCase):
    def test_accepts_extra_stack_ports(self):
        check_ports(8081, 5433)

    def test_rejects_main_stack_ports(self):
        with self.assertRaises(ValueError):
            check_ports(8080, 5433)
        with self.assertRaises(ValueError):
            check_ports(8081, 5432)

    def test_rejects_out_of_range(self):
        for port, db_port in ((80, 5433), (70000, 5433), (8081, 1023), (8081, 0)):
            with self.assertRaises(ValueError):
                check_ports(port, db_port)

    def test_dev_server_port(self):
        check_ports(8081, 5433, 5174)
        check_ports(8081, 5433, 5173)
        for dev_server_port in (80, 1023, 65536, 70000):
            with self.assertRaises(ValueError) as caught:
                check_ports(8081, 5433, dev_server_port)
            self.assertIn("--dev-server-port", str(caught.exception))

    def test_dev_server_port_not_a_stack_port(self):
        for dev_server_port in (8081, 5433):
            with self.assertRaises(ValueError) as caught:
                check_ports(8081, 5433, dev_server_port)
            self.assertIn("host port of this stack", str(caught.exception))

    def test_explicit_hint_only_for_derived_ports(self):
        cases = (
            ("--db-port", (8081, 70000, 5174)),
            ("--dev-server-port", (8081, 5433, 70000)),
        )
        for label, ports in cases:
            with self.subTest(label=label):
                with self.assertRaises(ValueError) as caught:
                    check_ports(*ports)
                self.assertNotIn("explicitly", str(caught.exception))
                with self.assertRaises(ValueError) as caught:
                    check_ports(*ports, derived={label})
                self.assertIn(f"(pass {label} explicitly)", str(caught.exception))


class DefaultsTests(SimpleTestCase):
    def test_postgres_port_offset(self):
        self.assertEqual(default_postgres_port(8081), 5433)
        self.assertEqual(default_postgres_port(8080), 5432)

    def test_dev_server_port_offset(self):
        self.assertEqual(default_dev_server_port(8081), 5174)
        self.assertEqual(default_dev_server_port(8089), 5182)
        self.assertEqual(default_dev_server_port(8080), 5173)

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
        once = rewrite_env(SOURCE, "x", 8081, 5433)
        twice = rewrite_env(once, "x", 8081, 5433).splitlines()
        for key in (
            "COMPOSE_PROJECT_NAME",
            "NGINX_HOST_PORT",
            "CSRF_COOKIE_NAME",
            "DEV_FRONTEND_ORIGINS",
        ):
            self.assertEqual(sum(line.startswith(f"{key}=") for line in twice), 1)
        self.assertEqual(twice.count(HEADER), 1)
        self.assertEqual("\n".join(twice) + "\n", once)

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
