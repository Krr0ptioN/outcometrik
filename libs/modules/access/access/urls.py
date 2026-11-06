from django.urls import path

from .api import AssignmentsView, RevokeView

urlpatterns = [
    path("assignments/", AssignmentsView.as_view()),
    path("roles/<uuid:pk>/", RevokeView.as_view(), {"kind": "roles"}),
    path("grants/<uuid:pk>/", RevokeView.as_view(), {"kind": "grants"}),
]
