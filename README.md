# Recipes CMS

A Django/Wagtail-based content management system for recipes with pluggable authentication (local accounts, Auth0, Zitadel) and REST API support.

## Features

### Authentication (`oidc_auth`)

Sign-in methods are pluggable. `AUTH_PROVIDERS` is a comma-separated subset of `local`
(username/password), `auth0` and `zitadel` (case-insensitive, duplicates dropped, default
`local,auth0`). An empty or unknown entry, or an enabled provider with missing variables,
stops the app at startup with an `ImproperlyConfigured` error naming every missing variable;
disabled providers need none.

- **Providers**: Auth0 and Zitadel via OpenID Connect (social-auth), plus local Django accounts. The Wagtail login page and the DRF login page show a button per enabled provider. `GET /api/auth/providers/` returns the enabled methods (`id`, `label`, `login_url`) so the frontend can render its own buttons.
- **One email, one provider**: a social login is refused, never merged, when the provider does not report `email_verified: true`, or when the email already belongs to a local user, to a user linked to another provider, or to another user of the same provider (compared case-insensitively). A user who is already logged in cannot link a second provider either.
- **Role sync**: on every login the user's provider roles are mapped to Wagtail groups (`ROLE_GROUP_MAP`: `editor` → Editors, `moderator` → Moderators); the `admin` role grants superuser and staff. Users without a role have no access. Roles are read from the ID token (falling back to the userinfo response): a list under `AUTH0_ROLES_CLAIM` for Auth0, the keys of the `urn:zitadel:iam:org:project:roles` object for Zitadel.
- **Logout**: the custom logout view logs out of Django and then of the user's own provider (Auth0 `/v2/logout`, Zitadel `/oidc/v1/end_session`); local users get a plain Django logout.
- **Local accounts**: when `local` is disabled, password login is off. Permissions keep working through a permissions-only backend. Local accounts have no 2FA, so disable `local` wherever 2FA is required and let the identity provider enforce it.
- **Emails**: `WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False`, so users cannot change their own email in the Wagtail account page; administrators (or the identity provider) manage emails. The Wagtail user forms and the `ensure_users` / `ensure_admin` commands refuse an email owned by a social user.
- **Comprehensive Test Suite**: Organized tests for configuration, pipeline, middleware, forms, views and login pages

#### Configuration

Set `AUTH_PROVIDERS` and the variables of each enabled provider:

```bash
AUTH_PROVIDERS=local,auth0,zitadel

# auth0
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=your-domain.auth0.com
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY=your-client-id
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET=your-client-secret
AUTH0_ROLES_CLAIM=https://recipes.example/roles

# zitadel (bare instance host, no scheme)
SOCIAL_AUTH_ZITADEL_DOMAIN=your-instance.zitadel.cloud
SOCIAL_AUTH_ZITADEL_KEY=your-client-id
SOCIAL_AUTH_ZITADEL_SECRET=your-client-secret
```

### Home (`home`)

- **HomePage Model**: Wagtail page model with title and description fields
- **REST API**: Read-only API endpoint for HomePage content
  - Endpoint: `/api/home/`
  - Serializes title and description fields
- **Translations**: One HomePage per content language (`en`, `de`, `fr`, `nl`), linked by Wagtail's `translation_key`

### Recipes (`recipes`)

- **RecipePage Model**: Wagtail page with preparation, times, servings and an orderable ingredient list
- **Multilingual Content**: Wagtail i18n (`WAGTAIL_I18N_ENABLED`) with English (default), German, French and Dutch; each language version lives under its locale's HomePage
- **Bulk Upload**: Create or update recipes and their translations from a JSON file, via the API or the `import_recipes` management command

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
├── oidc_auth/           # Pluggable authentication app (local, Auth0, Zitadel)
│   ├── tests/          # Organized test suite
│   ├── config.py       # AUTH_PROVIDERS parsing and startup checks
│   ├── backends.py     # Zitadel and permissions-only backends
│   ├── providers.py    # Provider registry: role readers, logout URLs
│   ├── pipeline.py     # Email ownership check and role sync
│   ├── middleware.py   # Turns refused logins into a redirect with a message
│   ├── ownership.py    # Email owner lookup (pipeline, forms, commands)
│   ├── redirects.py    # Safe redirect target validation
│   ├── forms.py        # Email checks for Wagtail user forms
│   └── views.py        # Per-provider logout, /api/auth/providers/
├── home/               # Home page app
│   ├── models.py       # HomePage model
│   ├── views.py        # API viewsets
│   ├── locales.py      # ?locale= query parameter handling
│   └── serializers.py  # REST serializers
├── recipes/            # Recipe pages app
│   ├── models.py       # RecipePage and RecipeIngredient models
│   ├── views.py        # API viewset incl. bulk upload
│   ├── serializers.py  # Read and bulk upload serializers
│   └── importer.py     # Bulk import service (API + import_recipes command)
└── recipe_cms/         # Project settings
    ├── settings/       # Environment-specific settings
    └── urls.py         # URL configuration

```

## API Endpoints

- `/api/home/` - HomePage content (GET); filter with `?locale=de` (default: `en`)
- `/api/recipes/` - Published recipes (GET); without `?locale=` returns all recipes grouped by locale as `{"locales": {"en": [...], "de": [...]}}`, with `?locale=de` returns a flat list for that locale. Detail (`/api/recipes/<id>/`) works for any locale. Each recipe includes `locale` and `translation_key`
- `/api/recipes/bulk-upload/` - Bulk create/update recipes (POST, see below)
- `/api/auth/providers/` - Enabled sign-in methods (GET, no authentication): `{"providers": [{"id", "label", "login_url"}]}`
- `/api/csrf/` - Returns a CSRF token (`{"csrfToken": ...}`) for cross-origin clients; send it back as `X-CSRFToken` on unsafe requests
- `/admin/` - Wagtail admin interface (requires authentication)
- `/admin/logout/` - Custom logout endpoint (also logs out of the user's sign-in provider)

### Bulk recipe upload

`POST /api/recipes/bulk-upload/` accepts either a JSON file in the multipart field `file` (max. 5 MB) or the same JSON as the request body. It requires a session of an Editors/Moderators (mapped roles), staff or superuser user and the `X-CSRFToken` header.

```bash
curl -b cookies.txt -H "X-CSRFToken: $TOKEN" -F file=@recipes.json \
  http://localhost:8000/api/recipes/bulk-upload/
```

Each entry groups the language versions of one recipe (max. 500 entries; a top-level list without `recipes` is accepted too):

```json
{
  "recipes": [
    {
      "translations": {
        "en": {
          "title": "Pancakes",
          "slug": "pancakes",
          "preparation": "<p>Mix and fry.</p>",
          "preparation_time": 10,
          "cooking_time": 15,
          "number_of_people": 4,
          "ingredients": [{"quantity": 200, "unit": "g", "name": "Flour"}],
          "live": true
        },
        "de": {"title": "Pfannkuchen", "ingredients": [{"quantity": 200, "unit": "g", "name": "Mehl"}]}
      }
    }
  ]
}
```

- Locale keys must be one of `en`, `de`, `fr`, `nl`. Only `title` is required; `slug` defaults to the slugified title and `live` to `true`.
- Recipes are matched by slug and locale: existing ones are updated (all fields and the ingredient list are replaced), new ones are created. Translations in one entry share a `translation_key`, so they appear as translations of each other in the Wagtail admin.
- Wagtail page permissions apply: users who may not publish (the default Editors group) get draft revisions for a moderator to publish; `live` in the response shows the result.
- The upload is all-or-nothing: on any error nothing is written and the response is `400` with errors keyed by entry index and locale.
- The response lists `created` and `updated` pages with `id`, `slug`, `locale`, `translation_key` and `live`.

The same file can be imported from the command line (no permission checks; pages are published as requested):

```bash
docker compose exec wagtail uv run manage.py import_recipes recipes.json
```

## Development

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (included with Docker Desktop)

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
SECRET_KEY=your-django-secret-key

# Sign-in methods: comma-separated subset of local, auth0, zitadel (default local,auth0).
# Each enabled provider's variables are required at startup; see "Authentication".
AUTH_PROVIDERS=local,auth0

# Auth0
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN=your-domain.auth0.com
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_KEY=your-client-id
SOCIAL_AUTH_AUTH0_OPENIDCONNECT_SECRET=your-client-secret
AUTH0_ROLES_CLAIM=https://recipes.example/roles
# A local dev Auth0 client needs its own post-login Action (the snippet in "Auth0 roles"
# below) using the same claim name as AUTH0_ROLES_CLAIM, with roles assigned in that
# tenant; the Pulumi-managed Action only affects the staging client.

# Zitadel (only needed when AUTH_PROVIDERS contains zitadel)
# SOCIAL_AUTH_ZITADEL_DOMAIN=your-instance.zitadel.cloud
# SOCIAL_AUTH_ZITADEL_KEY=your-client-id
# SOCIAL_AUTH_ZITADEL_SECRET=your-client-secret

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

#### Create or update an admin user

`ensure_admin` creates a superuser, or updates an existing user with that username to be an
active superuser with the given password (and email, if given). It is idempotent, so it can
run on every deploy. The password is read only from `DJANGO_ADMIN_PASSWORD`, so it never
shows up in the process list or shell history:

```bash
docker compose exec -e DJANGO_ADMIN_PASSWORD='…' wagtail \
  uv run manage.py ensure_admin --username admin --email admin@example.com
```

`--username` and `--email` default to `DJANGO_ADMIN_USERNAME` and `DJANGO_ADMIN_EMAIL`. The
password must pass Django's password validators.

#### Local users and the frontend

`docker compose up` runs `migrate` and then `ensure_users`, which creates or updates a
superuser, an Editors user and a Moderators user from `DJANGO_{ADMIN,EDITOR,MODERATOR}_{USERNAME,PASSWORD,EMAIL}`
in `.env` (see `.env.example`). A role whose username and password are unset is skipped.

A one-shot `frontend` service downloads the latest [recipes-frontend](https://github.com/globz-eu/recipes-frontend)
release into a volume that nginx serves at http://localhost:8080/frontend/. Set `FRONTEND_VERSION`
(e.g. `v0.5.0`) to pin a release; to re-download after a new release, run
`docker compose run --rm -e FRONTEND_FORCE=1 frontend` (or `docker compose up frontend` once the
latest tag changes, since the installed tag is recorded in the volume).

To work on the frontend against this backend, run `npm run dev` in `../recipes-frontend`
(http://localhost:5173/frontend/). The dev server proxies to nginx, and its login prompt offers a
username/password form for the users above. That form posts to `/api/dev-login/`, which only exists
when `DEV_PASSWORD_LOGIN` is true (set in `recipe_cms.settings.dev` only; it is off in production)
and is not part of the published frontend build.

### Running Tests

```bash
# Run all tests
docker compose exec wagtail uv run manage.py test

# Run oidc_auth tests
docker compose exec wagtail uv run manage.py test oidc_auth

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
- Browsers fetch media via nginx at `/media/`, which proxies to Django's `serve_media` view (`image_auth`). It checks that the user is authenticated and allowed (a mapped group such as Editors or Moderators, staff or superuser) before streaming the object from S3.
- `wagtail-storages` manages per-object ACLs so documents in private Wagtail collections are not publicly accessible.

#### S3_CUSTOM_DOMAIN

`S3_CUSTOM_DOMAIN` controls the base URL that Django generates for uploaded files. Set it to the public hostname and path prefix that nginx uses to serve media:

```bash
# Local dev (nginx on :8080, proxying /media/ to Django)
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

## Deployment

Staging runs on Scaleway and is managed by the Pulumi project in
[recipes-infrastructure](../recipes-infrastructure) (stack `staging`). The compose services map to:

| compose    | Scaleway                                                                |
|------------|-------------------------------------------------------------------------|
| `wagtail`  | Serverless Container (`staging.<domain>`) + Serverless Jobs for `migrate`, `collectstatic` and `ensure_admin` |
| `database` | Serverless SQL Database                                                 |
| `s3`       | Object Storage: private media bucket + public static bucket             |
| `nginx`    | Edge Services CDN (`static.staging.<domain>`) serving `/static/` and `/frontend/` |

Because Edge Services can't use a container as origin, the frontend is served from the static
host and calls the API cross-origin with credentials. The production settings read these
extra variables:

| Variable | Purpose |
|----------|---------|
| `ALLOWED_HOSTS` | Comma-separated hosts, e.g. `staging.example.com` |
| `CSRF_TRUSTED_ORIGINS` | Origins allowed to POST, e.g. `https://staging.example.com,https://static.staging.example.com` |
| `CORS_ALLOWED_ORIGINS` | Origins allowed to call the API with credentials (the frontend origin) |
| `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` | Extra hosts login/logout may redirect back to (the frontend host) |
| `STATIC_BUCKET_NAME`, `STATIC_CUSTOM_DOMAIN` | Collect static files to S3 and serve them from the CDN domain |
| `S3_REGION_NAME` | Object storage region (`fr-par` on Scaleway, `garage` locally) |
| `POSTGRES_SSLMODE` | libpq `sslmode` (`require` for Serverless SQL) |
| `WAGTAILADMIN_BASE_URL` | Public base URL of the admin |
| `AUTH_PROVIDERS` | Enabled sign-in methods, subset of `local`, `auth0`, `zitadel` (default `local,auth0`) |
| `SOCIAL_AUTH_AUTH0_OPENIDCONNECT_DOMAIN`, `_KEY`, `_SECRET` | Auth0 application; required when `auth0` is enabled |
| `AUTH0_ROLES_CLAIM` | Namespaced ID-token claim holding the user's Auth0 roles; required when `auth0` is enabled |
| `SOCIAL_AUTH_ZITADEL_DOMAIN`, `SOCIAL_AUTH_ZITADEL_KEY`, `SOCIAL_AUTH_ZITADEL_SECRET` | Zitadel instance host (no scheme), client ID and secret; required when `zitadel` is enabled |

The frontend lives in [recipes-frontend](https://github.com/globz-eu/recipes-frontend); compose downloads
its latest release and serves it at `/frontend/`. Its build is environment-independent: deployments use a
release and write a `config.json` pointing it at the API host.
Releases are built by CI on `v*.*.*` tags (`invoke bump`); see the infrastructure repo's README for deploying.

## Authentication Flow

1. User navigates to `/admin/` and picks an enabled sign-in method (or the frontend starts the login at a `login_url` from `/api/auth/providers/`)
2. Social login: the user authenticates at Auth0 or Zitadel and returns to `/complete/<backend>/`. The social auth pipeline then:
   - Refuses the login unless the provider reports a verified email that belongs to no other account (see below)
   - Creates a new Django user if needed
   - Reads the roles from the ID token (Auth0: the claim named by `AUTH0_ROLES_CLAIM`; Zitadel: `urn:zitadel:iam:org:project:roles`)
   - Adds or removes the user's Editors / Moderators groups to match the roles
   - Sets superuser and staff status according to the `admin` role
3. User is redirected to the Wagtail admin interface (or back to the `next` URL)
4. On logout, social users are redirected to their provider's logout endpoint; local users are logged out of Django only

### Refused logins

A social login is refused when the email is unverified (`email_unverified`), when it is already
owned by another account or sign-in method (`email_in_use`), or when a user who is already
signed in starts a social login (`already_signed_in`; they must sign out first). The same
code is used when the provider identity is already linked to a different user. A cancelled or
forbidden provider login (for example the user denies consent) gives the generic `login_failed`. For an existing
association the email the provider reports at each login is checked; the stored email is never
refreshed from the provider (social-auth protects `email`). A refused login redirects to the `next` URL given at login start
(only allowed hosts: the request host and `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS`) with
`auth_error=<code>` appended, so the frontend can show a message; without a safe `next` URL the user lands on the Wagtail login page with an error message.

Rollout note: existing users sign in through a provider that must send `email_verified: true`.
Auth0 and Zitadel do when the `email` scope is requested (Zitadel additionally needs
"User Info inside ID Token", see below); a provider that does not send it locks everybody out.

Before deploying, check for duplicate emails. Earlier versions did not prevent a local account
and an Auth0 user (or two Auth0 users) from sharing an email; now such a social login is refused
(`email_in_use`), `ensure_users` aborts with a `CommandError` (so the compose start
`migrate && ensure_users && runserver` fails) and the `ensure_admin` job fails when
`DJANGO_ADMIN_EMAIL` collides. Find duplicates (case-insensitive) with:

```bash
docker compose exec wagtail uv run manage.py shell -c "from django.contrib.auth import get_user_model; from django.db.models import Count; from django.db.models.functions import Lower; print(list(get_user_model().objects.annotate(e=Lower('email')).exclude(e='').values('e').annotate(n=Count('id')).filter(n__gt=1)))"
```

It must print `[]`. Otherwise change the email of, or delete, all but one account per address in
the Wagtail admin. The local `DJANGO_*_EMAIL` values must also differ from every email of an
identity-provider user, or the dev stack won't start.

The frontend gets relative `login_url`s from `/api/auth/providers/`; because it is cross-origin
in production it prefixes them with the API origin (it already does, via `apiUrl()`).

### Auth0 roles

Create the roles `admin`, `editor` and `moderator` in Auth0 (the recipes-infrastructure
Pulumi program does this) and assign them to users: User Management → Users → the user →
Roles → Assign Roles. A post-login Action must add the roles to the ID token under the
namespace configured as `AUTH0_ROLES_CLAIM`:

```js
exports.onExecutePostLogin = async (event, api) => {
  api.idToken.setCustomClaim("https://recipes.example/roles", event.authorization?.roles ?? []);
};
```

Roles are synced at login, so changes apply at the user's next login. Users without a mapped role
can log in but have no access (the API answers 403 with `code: "no_access"`). Deploy the
Action and assign roles before deploying this version. If `auth0` is enabled and
`AUTH0_ROLES_CLAIM` is unset, the app refuses to start; if it is set but roles are not
assigned yet, users lose access at their next login. Practical rule: deploy the infrastructure
(Action, roles, env var) and assign roles before bumping the CMS image.

Because superuser and staff follow the `admin` role on every social login, anyone given
superuser/staff by hand in Wagtail who logs in via Auth0 or Zitadel loses it at the next login
unless they hold the `admin` role.

### Zitadel setup

1. Create a project with the roles `admin`, `editor` and `moderator`, and grant them to users
   (Project → Authorizations).
2. In the project settings enable "Assert Roles on Authentication" so the roles are included
   in the tokens.
3. Create a Web application in the project (authentication method Code, with a client secret).
   In its settings enable "User roles inside ID Token" and "User Info inside ID Token" (the latter
   puts `email` and `email_verified` into the ID token). The `urn:zitadel:iam:org:project:roles`
   scope is requested automatically.
4. Redirect URI: `https://<host>/complete/zitadel/` (e.g. `http://localhost:8080/complete/zitadel/`
   locally). Post-logout redirect URIs: the URLs users are sent back to after logout, i.e. the
   admin URL and the frontend URL. Zitadel only accepts registered post-logout URIs (exact match),
   so every `next` URL used for logout (admin and frontend) must be registered; otherwise Zitadel
   shows an error page after the local logout.
5. Set `SOCIAL_AUTH_ZITADEL_DOMAIN` (bare instance host), `SOCIAL_AUTH_ZITADEL_KEY` (client ID)
   and `SOCIAL_AUTH_ZITADEL_SECRET`, and add `zitadel` to `AUTH_PROVIDERS`.

`ROLE_GROUP_MAP` (`editor` → Editors, `moderator` → Moderators) is shared by all providers, so
Zitadel and Auth0 roles with the same name map to the same groups.

### Local accounts

`local` enables username/password login for Django accounts (Wagtail admin, `ensure_users`,
`ensure_admin`). They have no 2FA; where 2FA is required, remove `local` from `AUTH_PROVIDERS`
and manage access through the identity provider.

The Docker image build runs `collectstatic` with `AUTH_PROVIDERS=local`, since no provider variables
exist at build time.
