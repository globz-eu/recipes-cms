from django.urls import path

from .views import check_permissions

urlpatterns = [
    path("", check_permissions, name="image-permissions"),
]
