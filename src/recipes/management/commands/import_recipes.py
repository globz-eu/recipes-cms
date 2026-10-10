import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from recipes.importer import RecipeImportError, import_recipes
from recipes.serializers import BulkUploadSerializer


class Command(BaseCommand):
    help = (
        "Create or update recipes from a JSON file, in the same format as the "
        "/api/recipes/bulk-upload/ endpoint. Recipes are matched by slug and "
        "locale; the import is all-or-nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path, help="Path to the JSON file.")

    def handle(self, *args, **options):
        path = options["path"]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise CommandError(f"Cannot read {path}: {error}")
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CommandError(f"Invalid JSON in {path}: {error}")
        if isinstance(payload, list):
            payload = {"recipes": payload}

        serializer = BulkUploadSerializer(data=payload)
        if not serializer.is_valid():
            raise CommandError(json.dumps(serializer.errors, indent=2))
        try:
            result = import_recipes(serializer.validated_data["recipes"])
        except RecipeImportError as error:
            raise CommandError(json.dumps(error.errors, indent=2, default=str))

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(result.created)} and updated "
                f"{len(result.updated)} recipe page(s)."
            )
        )
