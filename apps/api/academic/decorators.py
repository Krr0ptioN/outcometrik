import functools
import inspect
from collections.abc import Callable
from typing import Any

from .guards import guard, require_permission


def validate_payload(
    serializer_cls: type,
    *,
    partial: bool = False,
    pass_serializer: bool = False,
    data_getter: Callable[..., Any] | None = None,
    merge_data: Callable[..., dict[str, Any]] | None = None,
) -> Callable:
    """Validation interceptor decorator analogous to NestJS `@Body(ValidationPipe)`.

    Serializes and validates incoming request data before the action method executes.
    Passes validated data as `payload` (and optionally `serializer`) into the method kwargs.

    Arguments:
        serializer_cls: The DRF Serializer class to validate the payload against.
        partial: Whether validation allows partial updates (defaults to True on PATCH).
        pass_serializer: If True or if 'serializer' is in the method signature, injects
            the validated serializer instance as `serializer=...`.
        data_getter: Optional callable `(self, request, *args, **kwargs)` returning custom data
            dict to be validated instead of `request.data`.
        merge_data: Optional callable `(self, request, *args, **kwargs)` returning a dict
            to be merged into `request.data` before validation (useful for merging URL params).
    """

    def decorator(view_func: Callable) -> Callable:
        sig = inspect.signature(view_func)
        accepts_payload = "payload" in sig.parameters
        accepts_serializer = "serializer" in sig.parameters or pass_serializer

        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            context = (
                self.get_serializer_context() if hasattr(self, "get_serializer_context") else {}
            )
            is_partial = partial or getattr(request, "method", "").upper() == "PATCH"

            if data_getter is not None:
                data = data_getter(self, request, *args, **kwargs)
            else:
                data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
                if merge_data is not None:
                    extra = merge_data(self, request, *args, **kwargs)
                    data.update(extra)

            serializer = serializer_cls(data=data, context=context, partial=is_partial)
            serializer.is_valid(raise_exception=True)

            if accepts_payload:
                kwargs["payload"] = serializer.validated_data
            if accepts_serializer:
                kwargs["serializer"] = serializer

            return view_func(self, request, *args, **kwargs)

        return wrapper

    return decorator


# Convenience alias for NestJS-style naming
validate_dto = validate_payload
body = validate_payload

__all__ = [
    "body",
    "guard",
    "require_permission",
    "validate_dto",
    "validate_payload",
]
