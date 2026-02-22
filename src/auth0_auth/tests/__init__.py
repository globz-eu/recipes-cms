"""
Test suite for auth0_auth app.

This module imports all tests from separate test files for convenience.
Tests are organized into:
- test_views.py: Tests for views (CustomLogoutView)
- test_pipeline.py: Tests for pipeline functions (add_user_to_editors_group)
"""

from auth0_auth.tests.test_views import *  # noqa: F401, F403
from auth0_auth.tests.test_pipeline import *  # noqa: F401, F403
