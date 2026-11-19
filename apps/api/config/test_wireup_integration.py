import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIClient
from wireup import injectable
from wireup.integration.django import (
    get_app_container,
    get_request_container,
    wireup_middleware,
)


@injectable
class ContainerCheckService:
    def ping(self) -> str:
        return "wireup-ok"


def test_app_container_is_initialized():
    container = get_app_container()
    assert container is not None


def test_wireup_middleware_scopes_request():
    rf = RequestFactory()
    request = rf.get("/api/health/status")

    resolved_inside_request = False

    def dummy_view(req):
        nonlocal resolved_inside_request
        scoped = get_request_container()
        assert scoped is not None
        resolved_inside_request = True
        return HttpResponse("ok")

    wrapped = wireup_middleware(dummy_view)
    response = wrapped(request)
    assert response.status_code == 200
    assert resolved_inside_request is True


@pytest.mark.django_db
def test_health_endpoint_functions_with_wireup_middleware():
    client = APIClient()
    response = client.get("/api/health/status")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}
