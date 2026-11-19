from dataclasses import dataclass, field

from django.conf import settings
from wireup import injectable


@injectable
@dataclass(frozen=True)
class ApiConfig:
    """Type-safe application configuration provider (analogous to NestJS ConfigService)."""

    debug: bool = field(default_factory=lambda: getattr(settings, "DEBUG", False))
    secret_key: str = field(default_factory=lambda: getattr(settings, "SECRET_KEY", ""))
    allowed_hosts: list[str] = field(
        default_factory=lambda: getattr(settings, "ALLOWED_HOSTS", ["localhost", "127.0.0.1"])
    )
    db_conn_max_age: int = field(
        default_factory=lambda: (
            getattr(settings, "DATABASES", {}).get("default", {}).get("CONN_MAX_AGE", 60)
        )
    )
    celery_broker_url: str = field(
        default_factory=lambda: getattr(settings, "CELERY_BROKER_URL", "")
    )
    celery_result_backend: str = field(
        default_factory=lambda: getattr(settings, "CELERY_RESULT_BACKEND", "")
    )
