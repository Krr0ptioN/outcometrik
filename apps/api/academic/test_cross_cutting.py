from access.policy import AuthorizationService
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import RequestFactory
from rest_framework.views import APIView
from wireup.integration.django import get_app_container
from wireup.ioc.container.async_container import async_container_force_sync_scope

from academic.filters import AcademicExceptionFilter, academic_exception_handler
from academic.interceptors import AppLogger, intercept_logging
from config.config_service import ApiConfig


def test_api_config_injected():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        config = scoped.get(ApiConfig)
        assert config is not None
        assert isinstance(config.allowed_hosts, list)
        assert config.db_conn_max_age >= 0


def test_app_logger_injected():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        logger = scoped.get(AppLogger)
        assert logger is not None
        logger.info("Test log message", extra_param="value")


def test_authorization_service_injected():
    container = get_app_container()
    with async_container_force_sync_scope(container) as scoped:
        auth_service = scoped.get(AuthorizationService)
        assert auth_service is not None
        assert isinstance(auth_service, AuthorizationService)


def test_intercept_logging_decorator():
    logged_messages = []

    class MockLogger:
        def info(self, msg, **kwargs):
            logged_messages.append(msg)

    class DummyView:
        logger = MockLogger()

        @intercept_logging("custom_op")
        def handle(self, request):
            return "ok"

    rf = RequestFactory()
    req = rf.get("/")
    v = DummyView()
    res = v.handle(req)
    assert res == "ok"
    assert len(logged_messages) == 1
    assert "custom_op" in logged_messages[0]


def test_exception_handler_transforms_validation_error():
    exc = DjangoValidationError({"field": "Required"})
    resp = academic_exception_handler(exc, context={})
    assert resp is not None
    assert resp.status_code == 400
    assert resp["Cache-Control"] == "no-store"


def test_exception_handler_transforms_permission_denied():
    exc = DjangoPermissionDenied("Forbidden scope")
    resp = academic_exception_handler(exc, context={})
    assert resp is not None
    assert resp.status_code == 403
    assert resp["Cache-Control"] == "no-store"


def test_exception_filter_mixin():
    class TestAPIView(AcademicExceptionFilter, APIView):
        pass

    view = TestAPIView()
    exc = DjangoValidationError({"code": "Invalid"})
    resp = view.handle_exception(exc)
    assert resp.status_code == 400
    assert resp["Cache-Control"] == "no-store"
