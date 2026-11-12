# syntax=docker/dockerfile:1

FROM python:3.14-slim-trixie AS build

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
ARG DJANGO_SETTINGS_MODULE="recipe_cms.settings.production"
ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src .
# Build has no provider env vars, so enable only the one that needs none.
RUN AUTH_PROVIDERS=local /opt/venv/bin/python manage.py collectstatic --noinput --clear

FROM python:3.14-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH=/opt/venv/bin:$PATH
ARG DJANGO_SETTINGS_MODULE="recipe_cms.settings.production"
ENV DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE

WORKDIR /app
RUN useradd -m wagtail \
    && mkdir -p /app/media/images /app/media/original_images \
    && chown -R wagtail:wagtail /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=wagtail:wagtail /app/static /app/static
COPY --chown=wagtail:wagtail src .
USER wagtail

HEALTHCHECK --interval=30s --timeout=30s --start-interval=5s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["gunicorn", "recipe_cms.wsgi:application"]

EXPOSE 8000
