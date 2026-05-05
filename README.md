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
- **Wagtail 7.3**: CMS framework
- **Django REST Framework**: API development
- **Social Auth App Django**: OAuth/OpenID Connect integration
- **django-storages + wagtail-storages**: S3-compatible media storage via Garage
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

# Garage S3-compatible object storage
GARAGE_ADMIN_TOKEN=your-garage-admin-token
GARAGE_METRICS_TOKEN=your-garage-metrics-token
GARAGE_RPC_SECRET=your-garage-rpc-secret
S3_BUCKET_NAME=recipes-cms
S3_ACCESS_KEY=your-garage-access-key
S3_SECRET_KEY=your-garage-secret-key
S3_ENDPOINT_URL=http://s3:3900
S3_CUSTOM_DOMAIN=localhost:8080/media
S3_URL_PROTOCOL=http:
```

Copy `.env.example` to `.env` and fill in the values.

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
| `s3`       | Garage S3-compatible storage | 3900 (S3 API), 3902 (web), 3903 (admin) |

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

### Invoke Tasks

Common development tasks are automated with [Invoke](https://www.pyinvoke.org/). Run `uv run invoke -l` to list all available tasks.

| Task | Description |
|------|-------------|
| `invoke dev` | Start the development server via Docker Compose with file watching enabled (`--build` flag rebuilds images first) |
| `invoke format` | Format and auto-fix source code using `ruff` |
| `invoke bump` | Bump the project version, update the lockfile, and create an annotated git tag (`--part major\|minor\|patch`, default: `patch`) |

```bash
# Start dev server (rebuild images first)
uv run invoke dev --build

# Format code
uv run invoke format

# Bump the minor version
uv run invoke bump --part minor
```

### Stopping the Stack

```bash
# Stop containers
docker compose down

# Stop and remove volumes (resets database and static files)
docker compose down -v
```

### Object Storage (Garage)

Media files (images, documents) are stored in [Garage](https://garagehq.deuxfleurs.fr/), a self-hosted S3-compatible object store.

#### How it works

- The `wagtail` container uploads files directly to Garage on port 3900 (S3 API) using `django-storages` with the `S3Boto3Storage` backend.
- Browsers fetch media via nginx at `/media/`, which proxies to Garage's web endpoint (port 3902). This avoids exposing Garage directly and keeps the public URL stable.
- `wagtail-storages` manages per-object ACLs so documents in private Wagtail collections are not publicly accessible.

#### S3_CUSTOM_DOMAIN

`S3_CUSTOM_DOMAIN` controls the base URL that Django generates for uploaded files. Set it to the public hostname and path prefix that nginx uses to serve media:

```bash
# Local dev (nginx on :8080, proxying /media/ to Garage)
S3_CUSTOM_DOMAIN=localhost:8080/media
S3_URL_PROTOCOL=http:

# Production
S3_CUSTOM_DOMAIN=your-domain.com/media
S3_URL_PROTOCOL=https:
```

#### Provisioning Garage for a new environment

```bash
# 1. Start the stack
docker compose up -d

# 2. Apply layout (single-node cluster)
docker compose exec s3 /garage layout assign -z dc1 -c 1G $(docker compose exec s3 /garage node id -q | head -c 16)
docker compose exec s3 /garage layout apply --version 1

# 3. Create bucket and access key
docker compose exec s3 /garage bucket create recipes-cms
docker compose exec s3 /garage key create recipes-cms-key
docker compose exec s3 /garage bucket allow --read --write --owner recipes-cms --key recipes-cms-key


# 5. Copy the printed key ID / secret into your .env as S3_ACCESS_KEY / S3_SECRET_KEY
```

#### Fix document ACLs

If documents were uploaded before `wagtail-storages` was active, run:

```bash
docker compose exec wagtail uv run manage.py fix_document_acls
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
