# Recipes CMS

A Django/Wagtail-based content management system for recipes with Auth0 authentication and REST API support.

## Features

### Authentication (`auth0_auth`)

- **Auth0 Integration**: OAuth2/OpenID Connect authentication via Auth0
- **Custom Logout View**: Handles both Django and Auth0 logout flows
  - Redirects Auth0 users to Auth0's logout endpoint
  - Falls back to standard Django logout for non-Auth0 users
  - Graceful error handling for misconfigured settings
- **Automated User Provisioning**: New users are automatically added to the Wagtail Editors group via a social auth pipeline
- **Comprehensive Test Suite**: Organized tests for views and pipeline functions

#### Configuration

Set the following environment variables:

```bash
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=your-domain.auth0.com
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY=your-client-id
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET=your-client-secret
```

### Home (`home`)

- **HomePage Model**: Wagtail page model with title and description fields
- **REST API**: Read-only API endpoint for HomePage content
  - Endpoint: `/api/home/`
  - Serializes title and description fields
- **Page Constraints**: Single instance home page (max_count = 1)

## Tech Stack

- **Django 6.x**: Web framework
- **Wagtail 7.3rc1**: CMS framework
- **Django REST Framework**: API development
- **Social Auth App Django**: OAuth/OpenID Connect integration
- **Python 3.14+**: Programming language

## Project Structure

```
src/
├── auth0_auth/          # Auth0 authentication app
│   ├── tests/          # Organized test suite
│   │   ├── test_views.py      # View tests
│   │   └── test_pipeline.py   # Pipeline function tests
│   ├── pipeline.py     # Social auth pipeline functions
│   └── views.py        # Custom logout view
├── home/               # Home page app
│   ├── models.py       # HomePage model
│   ├── views.py        # API viewsets
│   └── serializers.py  # REST serializers
└── recipe_cms/         # Project settings
    ├── settings/       # Environment-specific settings
    └── urls.py         # URL configuration

```

## API Endpoints

- `/api/home/` - HomePage content (GET)
- `/admin/` - Wagtail admin interface (requires authentication)
- `/admin/logout/` - Custom logout endpoint

## Development

### Running Tests

```bash
# Run all tests
uv run src/manage.py test

# Run auth0_auth tests
uv run src/manage.py test auth0_auth

# Run home tests
uv run src/manage.py test home
```

### Running the Development Server

```bash
uv run src/manage.py runserver
```

## Authentication Flow

1. User navigates to `/admin/`
2. User authenticates via Auth0
3. On first login, the social auth pipeline:
   - Creates a new Django user
   - Adds the user to the "Editors" group
   - Grants Wagtail editor permissions
4. User is redirected to the Wagtail admin interface
5. On logout, user is redirected to Auth0's logout endpoint (if Auth0 user)
