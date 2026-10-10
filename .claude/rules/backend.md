---
paths:
  - "src/**/*.py"
---

# Backend rules

- Content is multilingual. Any query or API endpoint returning pages must respect the locale: use `home.locales.get_requested_locale` for the `?locale=` parameter (default `en`) instead of reading the query string yourself.
- Pages of different languages are linked only through `translation_key`; never match translations by slug or title.
- Create and edit pages through Wagtail's revision workflow (`save_revision`, then `publish`/`unpublish`), not by saving the page directly, and check `page.permissions_for_user(user)` when a user is involved.
- `RecipePage` may only live under `home.HomePage` (`parent_page_types`). Create recipes via `homepage.add_child(instance=page)` so the treebeard path and depth stay valid.
- Wrap multi-object writes in `transaction.atomic()`. For all-or-nothing flows use the pattern in `recipes/importer.py`: per-item savepoints, collect errors, then `transaction.set_rollback(True)`.
- Schema changes need a migration, and anything that seeds locales or homepages belongs in a data migration, as in `home/migrations/0002` and `0004`. Never edit an applied migration.
- Settings go in `recipe_cms/settings/base.py`. Only environment-specific values go in `dev.py` or `production.py`, and secrets are read from environment variables.
- Tests use Django's test runner under `<app>/tests/test_*.py`, not pytest. Run `uv run invoke format` before finishing; ruff enforces import sorting.
