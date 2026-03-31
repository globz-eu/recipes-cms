from django.contrib import admin
from django.urls import include, path
from rest_framework import urls as rest_framework_urls
from rest_framework.routers import DefaultRouter
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from auth0_auth.views import CustomLogoutView
from home.views import HomeViewSet
from image_auth import urls as image_auth_urls
from image_auth.views import serve_media

router = DefaultRouter()
router.register("home", HomeViewSet, basename="home")
urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Override Wagtail admin logout before including wagtailadmin_urls
    path("admin/logout/", CustomLogoutView.as_view(), name="wagtailadmin_logout"),
    path("admin/", include(wagtailadmin_urls)),
    path("api/", include(router.urls)),
    path("image-auth/", include(image_auth_urls)),
    path("media/<path:image_path>", serve_media, name="serve-media"),
    path("documents/", include(wagtaildocs_urls)),
    # Override DRF logout to use Auth0-aware logout before including rest_framework urls
    path("api-auth/logout/", CustomLogoutView.as_view(), name="rest_framework_logout"),
    path("api-auth/", include(rest_framework_urls, namespace="rest_framework")),
    path("", include("social_django.urls", namespace="social")),
]


urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
