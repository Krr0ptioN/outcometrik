from django.urls import path

from .controllers import ReportExportController

urlpatterns = [path("reports/exports/", ReportExportController.as_view())]
