from django.urls import path

from .administration import (
    AccountsView,
    ActivateAccountView,
    CoordinatorAccountsView,
    CoordinatorDashboardView,
    DashboardView,
)
from .api import AssignmentsView, RevokeView

urlpatterns = [
    path("dashboard/", DashboardView.as_view()),
    path("accounts/", AccountsView.as_view()),
    path("accounts/<int:pk>/activate/", ActivateAccountView.as_view()),
    path("coordinator/", CoordinatorDashboardView.as_view()),
    path("coordinator/accounts/", CoordinatorAccountsView.as_view()),
    path("assignments/", AssignmentsView.as_view()),
    path("roles/<uuid:pk>/", RevokeView.as_view(), {"kind": "roles"}),
    path("grants/<uuid:pk>/", RevokeView.as_view(), {"kind": "grants"}),
]
