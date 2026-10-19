"""
Test suite for oidc_auth app.

This module imports all tests from separate test files for convenience.
Tests are organized into:
- test_views.py: Tests for views (CustomLogoutView)
- test_pipeline.py: Tests for pipeline functions (sync_roles)
- test_ownership_pipeline.py: Tests for enforce_email_ownership and ownership lookups
- test_middleware.py: Tests for LoginRefusedMiddleware
- test_backends.py, test_config.py: Tests for auth backends and settings helpers
"""

from oidc_auth.tests.test_pipeline import *  # noqa: F401, F403
from oidc_auth.tests.test_views import *  # noqa: F401, F403
