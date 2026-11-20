from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..decorators import controller, get, patch, post, scoped_permission, validate_payload
from ..serializers import CourseOfferingSerializer, EnrollmentSerializer
from ..services import CourseOfferingService, EnrollmentService, academic_service_provider
from .base import AcademicPagination


@controller("offerings", basename="offering")
class CourseOfferingController(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Controller for course offerings with constructor injection and guard protection."""

    serializer_class = CourseOfferingSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPagination

    def __init__(
        self,
        service: CourseOfferingService | None = None,
        enrollment_service: EnrollmentService | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(CourseOfferingService)
        self.enrollment_service = enrollment_service or academic_service_provider.provide(
            EnrollmentService
        )

    def get_queryset(self):
        filters = dict(self.request.query_params.items())
        return self.service.get_queryset(actor=self.request.user, **filters)

    @get()
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @get("{id}")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @post(
        permission_classes=[
            IsAuthenticated,
            scoped_permission("offering.manage", scope_field="program"),
        ]
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @patch("{id}", permission_classes=[IsAuthenticated, scoped_permission("offering.manage")])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @get("{id}/enrollments")
    def list_enrollments(self, request, pk=None):
        """Return roster rows for this offering."""
        offering = self.get_object()
        queryset = self.enrollment_service.get_queryset(actor=request.user, offering=offering)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            EnrollmentSerializer(page, many=True, context=self.get_serializer_context()).data
        )

    @post(
        "{id}/enrollments",
        permission_classes=[IsAuthenticated, scoped_permission("offering.manage")],
    )
    @validate_payload(
        EnrollmentSerializer,
        merge_data=lambda self, request, pk=None: {"offering": str(self.get_object().pk)},
    )
    def create_enrollment(self, request, pk=None, payload=None):
        """Add roster row for this offering."""
        enrollment = self.enrollment_service.create(actor=request.user, **payload)
        serializer = EnrollmentSerializer(enrollment, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.instance = self.service.create(**serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = self.service.update(
            instance=serializer.instance,
            **serializer.validated_data,
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
