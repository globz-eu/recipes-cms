import re
from pathlib import Path
from unittest import SkipTest

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE_DEV = ROOT / "compose.dev.yml"

if not DOCKERFILE.is_file():
    # The image holds src/ only; these are host-side checks.
    raise SkipTest("Dockerfile is not available (running inside the image)")

UV_WORD = re.compile(r"\buvx?\b")


def runtime_stage():
    """Return the Dockerfile lines after the last FROM (the image that ships)."""
    lines = DOCKERFILE.read_text().splitlines()
    last_from = max(i for i, line in enumerate(lines) if line.startswith("FROM "))
    return lines[last_from:]


def instruction(stage, keyword):
    return [line for line in stage if line.startswith(f"{keyword} ")]


class RuntimeImageTestCase(SimpleTestCase):
    def setUp(self):
        self.stage = runtime_stage()

    def test_runtime_stage_does_not_use_uv_or_apt(self):
        body = "\n".join(self.stage)
        self.assertIsNone(UV_WORD.search(body), body)
        self.assertNotIn("apt-get", body)

    def test_runs_gunicorn_from_the_venv_as_wagtail(self):
        self.assertEqual(
            instruction(self.stage, "CMD"),
            ['CMD ["gunicorn", "recipe_cms.wsgi:application"]'],
        )
        self.assertEqual(instruction(self.stage, "USER"), ["USER wagtail"])
        self.assertTrue(any("PATH=/opt/venv/bin:$PATH" in line for line in self.stage))

    def test_healthcheck_uses_python_not_curl(self):
        (healthcheck,) = instruction(self.stage, "HEALTHCHECK")
        self.assertIn('CMD ["python", "-c"', healthcheck)
        self.assertIn("http://localhost:8000/health", healthcheck)
        self.assertNotIn("curl", healthcheck)


class DevComposeCommandTestCase(SimpleTestCase):
    def test_container_commands_run_python_without_uv(self):
        command = COMPOSE_DEV.read_text().split("command:", 1)[1]
        self.assertIsNone(UV_WORD.search(command), command)
        for step in ("migrate", "ensure_users", "collectstatic", "runserver"):
            self.assertIn(f"python manage.py {step}", command)
