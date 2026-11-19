from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import exception_handler


def academic_exception_handler(exc, context):
    """Global exception filter (analogous to NestJS ExceptionFilter).

    Converts domain-level exceptions (Django ValidationError, PermissionDenied, etc.)
    into standard REST framework Response objects with proper status codes and headers.
    """
    if isinstance(exc, DjangoValidationError):
        details = getattr(exc, "message_dict", None) or exc.messages
        exc = ValidationError(details)
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied(str(exc))

    response = exception_handler(exc, context)
    if response is not None:
        response["Cache-Control"] = "no-store"
    return response


class AcademicExceptionFilter:
    """Exception filter mixin for controllers and class-based views."""

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            details = getattr(exc, "message_dict", None) or exc.messages
            exc = ValidationError(details)
        elif isinstance(exc, DjangoPermissionDenied):
            exc = PermissionDenied(str(exc))

        response = super().handle_exception(exc)
        if response is not None:
            response["Cache-Control"] = "no-store"
        return response
