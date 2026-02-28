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

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
SECRET_KEY=your-django-secret-key

# Auth0
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=your-domain.auth0.com
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY=your-client-id
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET=your-client-secret

# PostgreSQL
POSTGRES_USER=recipes
POSTGRES_PASSWORD=recipes
POSTGRES_DB=recipes
POSTGRES_HOST=database
```

### Starting the Stack

```bash
docker compose up
```

This starts three services:

| Service    | Description                  | Port  |
|------------|------------------------------|-------|
| `wagtail`  | Django/Wagtail app server    | 8000  |
| `nginx`    | Reverse proxy / static files | 8080  |
| `database` | PostgreSQL 18                | 5432  |

The admin interface is available at http://localhost:8080/admin/.

### Live Reload (file sync)

Use Docker Compose Watch to automatically sync local source changes into the container:

```bash
docker compose watch
```

Changes to `src/` are synced into the running container without requiring a restart. Changes to `config/nginx/nginx.conf` trigger an nginx restart.

### Running Management Commands

```bash
# Open a shell inside the wagtail container
docker compose exec wagtail /bin/bash

# Or run a command directly
docker compose exec wagtail uv run manage.py migrate
docker compose exec wagtail uv run manage.py createsuperuser
docker compose exec wagtail uv run manage.py collectstatic
```

### Running Tests

```bash
# Run all tests
docker compose exec wagtail uv run manage.py test

# Run auth0_auth tests
docker compose exec wagtail uv run manage.py test auth0_auth

# Run home tests
docker compose exec wagtail uv run manage.py test home
```

### Stopping the Stack

```bash
# Stop containers
docker compose down

# Stop and remove volumes (resets database and static files)
docker compose down -v
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
