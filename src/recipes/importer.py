import uuid
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from home.models import HomePage

from .models import RecipeIngredient, RecipePage

PAGE_FIELDS = [
    "title",
    "preparation",
    "preparation_time",
    "cooking_time",
    "number_of_people",
]


class RecipeImportError(Exception):
    """Raised when an upload cannot be imported; nothing has been written."""

    def __init__(self, errors: dict):
        super().__init__(errors)
        self.errors = errors


@dataclass
class ImportResult:
    created: list[dict] = field(default_factory=list)
    updated: list[dict] = field(default_factory=list)


def _summary(page: RecipePage) -> dict:
    return {
        "id": page.pk,
        "slug": page.slug,
        "locale": page.locale.language_code,
        "translation_key": str(page.translation_key),
        "live": page.live,
    }


def _apply_fields(page: RecipePage, data: dict) -> None:
    for name in PAGE_FIELDS:
        setattr(page, name, data[name])
    page.slug = data["slug"]
    page.ingredients = [RecipeIngredient(**item) for item in data["ingredients"]]


def _save(page: RecipePage, live: bool, user) -> None:
    """
    Saves a revision and publishes or unpublishes it as requested, as far as
    the user's Wagtail page permissions allow. Users who may not publish (e.g.
    Editors) leave a draft revision for a moderator. Without a user (management
    command) no permission checks apply.
    """
    permissions = page.permissions_for_user(user) if user else None
    revision = page.save_revision(user=user)
    if live and (permissions is None or permissions.can_publish()):
        revision.publish(user=user)
        page.refresh_from_db(fields=["live", "has_unpublished_changes"])
    elif (
        not live and page.live and (permissions is None or permissions.can_unpublish())
    ):
        page.unpublish(user=user)


def _import_group(group: dict, homepages: dict, result: ImportResult, user) -> None:
    translations = group["translations"]
    existing = {
        code: RecipePage.objects.child_of(homepages[code])
        .filter(slug=data["slug"])
        .first()
        for code, data in translations.items()
    }

    keys = {page.translation_key for page in existing.values() if page}
    if len(keys) > 1:
        raise RecipeImportError(
            {
                "translations": [
                    "These slugs belong to different existing recipes: "
                    + ", ".join(
                        f"{page.slug} ({code})"
                        for code, page in existing.items()
                        if page
                    )
                ]
            }
        )
    translation_key = keys.pop() if keys else uuid.uuid4()

    for code, data in translations.items():
        page = existing[code]
        if page is None:
            other = RecipePage.objects.filter(
                translation_key=translation_key, locale=homepages[code].locale
            ).first()
            if other:
                raise RecipeImportError(
                    {
                        "translations": {
                            code: [
                                f"This recipe already has a '{code}' translation "
                                f"with slug '{other.slug}'."
                            ]
                        }
                    }
                )
            if (
                user
                and not homepages[code].permissions_for_user(user).can_add_subpage()
            ):
                raise RecipeImportError(
                    {"translations": {code: ["You may not add recipes here."]}}
                )
            # Created unpublished; _save publishes it if the user may do so
            page = RecipePage(
                locale=homepages[code].locale,
                translation_key=translation_key,
                live=False,
            )
            _apply_fields(page, data)
            homepages[code].add_child(instance=page)
            _save(page, data["live"], user)
            result.created.append(_summary(page))
        else:
            if user and not page.permissions_for_user(user).can_edit():
                raise RecipeImportError(
                    {"translations": {code: [f"You may not edit '{page.slug}'."]}}
                )
            _apply_fields(page, data)
            _save(page, data["live"], user)
            result.updated.append(_summary(page))


def import_recipes(groups: list[dict], user=None) -> ImportResult:
    """
    Creates or updates recipes from validated BulkUploadSerializer data.

    Recipes are matched by (slug, locale). Translations within a group are
    linked through a shared translation_key. The import is all-or-nothing:
    on any error the transaction is rolled back and RecipeImportError carries
    the errors keyed by group index.
    """
    language_codes = {code for group in groups for code in group["translations"]}
    homepages: dict[str, HomePage] = {}
    for homepage in (
        HomePage.objects.filter(depth=2, locale__language_code__in=language_codes)
        .select_related("locale")
        .order_by("path")
    ):
        homepages.setdefault(homepage.locale.language_code, homepage)
    missing = sorted(language_codes - set(homepages))
    if missing:
        raise RecipeImportError(
            {
                "non_field_errors": [
                    f"No homepage exists for locale(s): {', '.join(missing)}."
                ]
            }
        )

    result = ImportResult()
    errors = {}
    with transaction.atomic():
        for index, group in enumerate(groups):
            try:
                with transaction.atomic():
                    _import_group(group, homepages, result, user)
            except RecipeImportError as error:
                errors[index] = error.errors
            except DjangoValidationError as error:
                errors[index] = {"translations": error.messages}
        if errors:
            transaction.set_rollback(True)
    if errors:
        raise RecipeImportError({"recipes": errors})
    return result
