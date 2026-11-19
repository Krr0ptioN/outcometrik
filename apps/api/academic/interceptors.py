import functools
import logging
import time
from collections.abc import Callable

from wireup import injectable


@injectable
class AppLogger:
    """Injectable structured logger service (analogous to NestJS Logger service)."""

    def __init__(self, name: str = "outcometrik"):
        self._logger = logging.getLogger(name)

    def info(self, msg: str, **kwargs):
        self._logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs):
        self._logger.warning(msg, extra=kwargs)

    def error(self, msg: str, **kwargs):
        self._logger.error(msg, extra=kwargs)

    def debug(self, msg: str, **kwargs):
        self._logger.debug(msg, extra=kwargs)


def intercept_logging(operation_name: str | None = None) -> Callable:
    """Execution timing and audit logging interceptor (analogous to NestJS LoggingInterceptor)."""

    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            op = operation_name or getattr(view_func, "__name__", "operation")
            start = time.perf_counter()
            try:
                response = view_func(self, request, *args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                logger = getattr(self, "logger", None)
                if logger and hasattr(logger, "info"):
                    logger.info(
                        f"Action '{op}' executed successfully in {duration_ms:.2f}ms",
                        user=getattr(request, "user", None),
                    )
                return response
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                logger = getattr(self, "logger", None)
                if logger and hasattr(logger, "error"):
                    logger.error(f"Action '{op}' failed after {duration_ms:.2f}ms: {exc}")
                raise

        return wrapper

    return decorator
