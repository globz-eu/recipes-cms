from django.urls import path
from .views import CustomLogoutView

app_name = "login"

urlpatterns = [
    path("logout/", CustomLogoutView.as_view(), name="logout"),
]
