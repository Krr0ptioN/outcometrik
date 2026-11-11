from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from ..services import academic_service_provider


class AcademicPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class AcademicController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HTTP adapter shared by resource controllers; domain operations are delegated."""

    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination
    filter_fields: tuple[str, ...] = ()
    ordering = ("created_at", "id")
    service_class = None
    service_provider = academic_service_provider

    def get_service(self, service_class=None):
        return self.service_provider.provide(
            service_class or self.service_class,
            actor=self.request.user,
        )

    def get_queryset(self):
        queryset = self.get_service().get_queryset()
        if self.action == "list":
            filters = {
                name: self.request.query_params[name]
                for name in self.filter_fields
                if name in self.request.query_params
            }
            queryset = queryset.filter(**filters)
        return queryset.order_by(*self.ordering)

    @staticmethod
    def raise_validation_error(exc):
        if isinstance(exc, DjangoValidationError):
            details = getattr(exc, "message_dict", None) or exc.messages
            raise ValidationError(details) from exc
        raise exc

    def perform_create(self, serializer):
        try:
            serializer.instance = self.get_service().create(**serializer.validated_data)
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)

    def perform_update(self, serializer):
        try:
            serializer.instance = self.get_service().update(
                instance=serializer.instance,
                **serializer.validated_data,
            )
        except DjangoValidationError as exc:
            self.raise_validation_error(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
