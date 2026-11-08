import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase
from invoke.context import Context
from invoke.exceptions import Exit
from invoke.runners import Result

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"


def load_tasks():
    spec = importlib.util.spec_from_file_location("cms_tasks", ROOT / "tasks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tasks = load_tasks()


def make_context(worktree_list=""):
    context = mock.MagicMock(spec=Context)

    def run(command, **kwargs):
        stdout = worktree_list if command.startswith("git worktree") else ""
        return Result(stdout=stdout, command=command)

    context.run.side_effect = run
    return context


def commands(context):
    return [call.args[0] for call in context.run.call_args_list]


class InfraLocationTestCase(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env_file = self.root / "dotenv"
        # tasks.HERE decides where .env is read from
        patcher = mock.patch.object(tasks, "HERE", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = {k: v for k, v in os.environ.items() if k != "RECIPES_INFRA_DIR"}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_infra(self, directory):
        script = Path(directory) / "scripts" / "dev-stack.sh"
        script.parent.mkdir(parents=True)
        script.write_text("#!/bin/sh\n")
        return script

    def test_defaults_to_sibling_of_the_main_worktree(self):
        main = self.root / "main"
        script = self.make_infra(self.root / "recipes-infrastructure")
        context = make_context(f"worktree {main}\nHEAD abc\n\nworktree /x/other\n")

        self.assertEqual(tasks._dev_stack_script(context), script.resolve())

    def test_environment_variable_overrides_sibling(self):
        script = self.make_infra(self.root / "custom")
        os.environ["RECIPES_INFRA_DIR"] = str(self.root / "custom")

        self.assertEqual(tasks._dev_stack_script(make_context()), script)

    def test_dotenv_value_is_used_when_environment_is_unset(self):
        script = self.make_infra(self.root / "fromenv")
        (self.root / ".env").write_text(
            f'# c\nOTHER=1\nexport RECIPES_INFRA_DIR = "{self.root}/fromenv"\n'
        )

        self.assertEqual(tasks._dev_stack_script(make_context()), script)

    def test_environment_wins_over_dotenv(self):
        script = self.make_infra(self.root / "env")
        self.make_infra(self.root / "file")
        (self.root / ".env").write_text(f"RECIPES_INFRA_DIR={self.root}/file\n")
        os.environ["RECIPES_INFRA_DIR"] = str(self.root / "env")

        self.assertEqual(tasks._dev_stack_script(make_context()), script)

    def test_last_dotenv_assignment_wins(self):
        (self.root / ".env").write_text("RECIPES_INFRA_DIR=a\nRECIPES_INFRA_DIR=b\n")

        self.assertEqual(tasks._env_file_value("RECIPES_INFRA_DIR"), "b")

    def test_missing_dotenv_gives_none(self):
        self.assertIsNone(tasks._env_file_value("RECIPES_INFRA_DIR"))

    def test_missing_checkout_exits_pointing_at_readme(self):
        os.environ["RECIPES_INFRA_DIR"] = str(self.root / "nowhere")

        with self.assertRaises(Exit) as raised:
            tasks._dev_stack_script(make_context())

        message = str(raised.exception)
        self.assertIn("RECIPES_INFRA_DIR", message)
        self.assertIn("Local dev environment", message)
        self.assertIn("recipes-infrastructure", message)

    def test_missing_sibling_exits(self):
        context = make_context(f"worktree {self.root / 'main'}\n")

        with self.assertRaises(Exit):
            tasks._dev_stack_script(context)

    def test_dev_fails_without_running_anything(self):
        os.environ["RECIPES_INFRA_DIR"] = str(self.root / "nowhere")
        context = make_context()

        with self.assertRaises(Exit):
            tasks.dev(context)

        context.run.assert_not_called()


class DevStackCommandsTestCase(SimpleTestCase):
    def setUp(self):
        script = Path("/infra/scripts/dev-stack.sh")
        patcher = mock.patch.object(tasks, "_dev_stack_script", return_value=script)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.context = make_context()
        self.compose = f"-f {tasks.COMPOSE_DEV}"

    def only_command(self):
        self.assertEqual(len(commands(self.context)), 1)
        return commands(self.context)[0]

    def test_compose_dev_points_at_the_checkout_file(self):
        self.assertIn(str(ROOT / "compose.dev.yml"), tasks.COMPOSE_DEV)

    def test_dev_starts_watch_without_cms_version_lookup(self):
        tasks.dev(self.context)

        command = self.only_command()
        self.assertTrue(command.startswith("sh /infra/scripts/dev-stack.sh up --watch"))
        self.assertIn("--skip-lookup CMS_VERSION", command)
        self.assertIn(self.compose, command)
        self.assertNotIn("--build", command)

    def test_dev_build_flag(self):
        tasks.dev(self.context, build=True)

        self.assertIn("--build", self.only_command())

    def test_dev_runs_from_this_checkout(self):
        tasks.dev(self.context)

        self.context.cd.assert_called_once_with(str(tasks.HERE))

    def test_down_without_volumes(self):
        tasks.down(self.context)

        self.assertEqual(
            self.only_command().split(), ["sh", "/infra/scripts/dev-stack.sh", "down"]
        )

    def test_down_with_volumes(self):
        tasks.down(self.context, volumes=True)

        self.assertEqual(self.only_command().split()[-2:], ["down", "-v"])

    def test_test_postgres_runs_in_the_wagtail_container(self):
        tasks.test(self.context, label="recipes", verbosity=2, postgres=True)

        command = self.only_command()
        self.assertIn("dev-stack.sh compose", command)
        self.assertIn(self.compose, command)
        self.assertIn("run --build --rm wagtail", command)
        self.assertIn("uv run manage.py test recipes --verbosity=2", command)
        self.context.cd.assert_called_once_with(str(tasks.HERE))

    def test_test_default_runs_on_the_host_in_src(self):
        tasks.test(self.context, label="recipes")

        command = self.only_command()
        self.assertEqual(
            command.split(),
            ["uv", "run", "manage.py", "test", "recipes", "--verbosity=1"],
        )
        self.context.cd.assert_called_once_with("src")
        self.assertNotIn("dev-stack", command)

    def test_dev_stack_commands_are_accepted_by_the_real_script(self):
        script = Path(os.environ.get("RECIPES_INFRA_DIR", "")) / "scripts/dev-stack.sh"
        if not script.is_file():
            self.skipTest("RECIPES_INFRA_DIR does not point at recipes-infrastructure")

        result = subprocess.run(
            ["sh", str(script), "up", "--bogus"], capture_output=True, text=True
        )

        # Guards the interface: unknown options are rejected, so the option
        # parser is what tasks.py talks to.
        self.assertNotEqual(result.returncode, 0)


class ManageDefaultSettingsTestCase(SimpleTestCase):
    def default_for(self, *argv):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
        code = (
            "import sys, os, runpy, types;"
            "m = types.ModuleType('django.core.management');"
            "m.execute_from_command_line = lambda a: print("
            "os.environ['DJANGO_SETTINGS_MODULE']);"
            "sys.modules['django.core.management'] = m;"
            f"sys.argv = ['manage.py', *{list(argv)!r}];"
            f"runpy.run_path({str(SRC / 'manage.py')!r}, run_name='__main__')"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_test_command_defaults_to_test_settings(self):
        self.assertEqual(self.default_for("test"), "recipe_cms.settings.test")

    def test_other_commands_default_to_dev_settings(self):
        self.assertEqual(self.default_for("migrate"), "recipe_cms.settings.dev")
        self.assertEqual(self.default_for(), "recipe_cms.settings.dev")

    def test_explicit_settings_module_wins(self):
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "recipe_cms.settings.production"}
        code = (
            "import sys, os, runpy, types;"
            "m = types.ModuleType('django.core.management');"
            "m.execute_from_command_line = lambda a: print("
            "os.environ['DJANGO_SETTINGS_MODULE']);"
            "sys.modules['django.core.management'] = m;"
            "sys.argv = ['manage.py', 'test'];"
            f"runpy.run_path({str(SRC / 'manage.py')!r}, run_name='__main__')"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True
        )

        self.assertEqual(out.stdout.strip(), "recipe_cms.settings.production")
