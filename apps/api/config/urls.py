from access.identity import LoginView, LogoutView, SessionView
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/auth/session/", SessionView.as_view()),
    path("api/auth/login/", LoginView.as_view()),
    path("api/auth/logout/", LogoutView.as_view()),
    path("admin/", admin.site.urls),
    path("api/health/", include("health.urls")),
    path("api/access/", include("access.urls")),
    path("api/v1/", include("academic.urls")),
]
