import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_status_endpoint():
    response = Client().get("/api/health/status")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_health_status_does_not_expose_dependency_details():
    response = Client().get("/api/health/status")

    assert set(response.json()) == {"status"}
