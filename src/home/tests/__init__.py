"""
Test suite for home app.

This module imports all tests from separate test files for convenience.
Tests are organized into:
- test_views_and_models.py: Tests for views and models (HomeViewSetTests, HomeSetUpTests)
- test_permissions.py: Tests for permission classes (IsEditorOrAdminPermissionTests)
"""

from home.tests.test_views_and_models import *  # noqa: F401, F403
from home.tests.test_permissions import *  # noqa: F401, F403
