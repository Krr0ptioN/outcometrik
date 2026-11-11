from access.identity import user_data
from access.models import DirectCapabilityGrant, RoleAssignment, Scope
from access.policy import authorization
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import scoping, services
from .access_control import require
from .models import (
    AcademicTerm,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Institution,
    InstructorAssignment,
    Program,
    ProgramCourse,
    ProgramMembership,
)
from .permissions import CanManageAcademicStructure
from .serializers import (
    AcademicTermSerializer,
    CourseOfferingSerializer,
    CourseSerializer,
    DepartmentSerializer,
    EnrollmentSerializer,
    EnrollmentStatusUpdateSerializer,
    InstitutionSerializer,
    InstructorAssignmentSerializer,
    ProgramCourseSerializer,
    ProgramMembershipSerializer,
    ProgramSerializer,
)


class AcademicPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class AcademicViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Create/list/retrieve/update only. There is deliberately no DELETE: history is archived."""

    permission_classes = [CanManageAcademicStructure]
    pagination_class = AcademicPagination
    filter_fields: tuple[str, ...] = ()
    ordering = ("created_at", "id")

    def object_write_scope(self, obj):
        if isinstance(obj, Institution):
            return "access.manage", obj.pk
        if isinstance(obj, Department):
            return "access.manage", obj.institution_id
        if isinstance(obj, AcademicTerm):
            return "access.manage", obj.institution_id
        if isinstance(obj, Course):
            return "access.manage", obj.home_department.institution_id
        if isinstance(obj, Program):
            return "program.manage", obj.pk
        if isinstance(obj, (ProgramCourse, ProgramMembership)):
            return "program.manage", obj.program_id
        if isinstance(obj, CourseOffering):
            return "offering.manage", obj.pk
        if isinstance(obj, InstructorAssignment):
            return "access.manage", obj.offering_id
        return "offering.manage", obj.offering_id

    def create_write_scope(self, data):
        model = self.queryset.model
        if model is Institution:
            from access.models import Scope

            scope = Scope.objects.filter(kind=Scope.Kind.INSTITUTION, label=data["name"]).first()
            return "access.manage", scope.pk if scope else None
        if model is Department or model is AcademicTerm:
            return "access.manage", data["institution"].pk
        if model is Course:
            return "access.manage", data["home_department"].institution_id
        if model is Program:
            return "program.manage", data["department"].institution_id
        if model in (ProgramCourse, ProgramMembership):
            return "program.manage", data["program"].pk
        if model is CourseOffering:
            return "offering.manage", data["program"].pk
        if model is InstructorAssignment:
            return "access.manage", data["offering"].pk
        if model is Enrollment:
            return "offering.manage", data["offering"].pk
        return "access.manage", None

    def perform_create(self, serializer):
        capability, scope_id = self.create_write_scope(serializer.validated_data)
        if scope_id is None:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Create institution scopes through trusted bootstrap.")
        require(self.request.user, capability, scope_id)
        serializer.save()

    def perform_update(self, serializer):
        capability, scope_id = self.object_write_scope(serializer.instance)
        require(self.request.user, capability, scope_id)
        serializer.save()

    def scope_queryset(self, queryset):
        return queryset

    def get_queryset(self):
        queryset = self.scope_queryset(self.queryset.all())
        if self.action == "list":
            filters = {
                name: self.request.query_params[name]
                for name in self.filter_fields
                if name in self.request.query_params
            }
            queryset = queryset.filter(**filters)
        return queryset.order_by(*self.ordering)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class InstitutionViewSet(AcademicViewSet):
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
    filter_fields = ("code",)

    def scope_queryset(self, queryset):
        return scoping.scope_institutions(self.request.user, queryset)


class DepartmentViewSet(AcademicViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    filter_fields = ("institution", "code")

    def scope_queryset(self, queryset):
        return scoping.scope_departments(self.request.user, queryset)


class ProgramViewSet(AcademicViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    filter_fields = ("department", "status", "code")

    def scope_queryset(self, queryset):
        return scoping.scope_programs(self.request.user, queryset)


class AcademicTermViewSet(AcademicViewSet):
    queryset = AcademicTerm.objects.all()
    serializer_class = AcademicTermSerializer
    filter_fields = ("institution", "year", "season")

    def scope_queryset(self, queryset):
        return scoping.scope_terms(self.request.user, queryset)


class CourseViewSet(AcademicViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    filter_fields = ("home_department", "code", "active")

    def scope_queryset(self, queryset):
        return scoping.scope_courses(self.request.user, queryset)


class ProgramCourseViewSet(AcademicViewSet):
    queryset = ProgramCourse.objects.all()
    serializer_class = ProgramCourseSerializer
    filter_fields = ("program", "course", "status")

    def scope_queryset(self, queryset):
        programs = scoping.scope_programs(self.request.user, Program.objects.all())
        return queryset.filter(program__in=programs)


class ProgramMembershipViewSet(AcademicViewSet):
    queryset = ProgramMembership.objects.all()
    serializer_class = ProgramMembershipSerializer
    filter_fields = ("program", "user", "status")

    def scope_queryset(self, queryset):
        return scoping.scope_memberships(self.request.user, queryset)


class CourseOfferingViewSet(AcademicViewSet):
    queryset = CourseOffering.objects.all()
    serializer_class = CourseOfferingSerializer
    filter_fields = ("program", "course", "term", "section", "status")

    def scope_queryset(self, queryset):
        return scoping.scope_offerings(self.request.user, queryset)

    @action(detail=True, methods=["get", "post"], url_path="enrollments")
    def enrollments(self, request, pk=None):
        """Roster of one offering (PRD: GET/POST /offerings/{id}/enrollments)."""
        offering = self.get_object()
        if request.method == "POST":
            serializer = EnrollmentSerializer(
                data={**request.data, "offering": str(offering.pk)},
                context=self.get_serializer_context(),
            )
            serializer.is_valid(raise_exception=True)
            require(request.user, "offering.manage", offering.pk)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        queryset = scoping.scope_enrollments(
            request.user, Enrollment.objects.filter(offering=offering)
        ).order_by("created_at", "id")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(
            EnrollmentSerializer(page, many=True, context=self.get_serializer_context()).data
        )


class InstructorAssignmentViewSet(AcademicViewSet):
    queryset = InstructorAssignment.objects.all()
    serializer_class = InstructorAssignmentSerializer
    filter_fields = ("offering", "user", "assignment_role")

    def scope_queryset(self, queryset):
        return scoping.scope_assignments(self.request.user, queryset)

    def create_write_scope(self, data):
        return "access.manage", data["offering"].pk


class EnrollmentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Roster rows. Status changes go through the policy service, never a raw update."""

    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer
    permission_classes = [CanManageAcademicStructure]
    pagination_class = AcademicPagination
    filter_fields = ("offering", "student", "status", "eligible_for_outcomes")

    def object_write_scope(self, obj):
        return "grades.edit", obj.offering_id

    def get_queryset(self):
        queryset = scoping.scope_enrollments(self.request.user, self.queryset.all())
        if self.action == "list":
            filters = {
                name: self.request.query_params[name]
                for name in self.filter_fields
                if name in self.request.query_params
            }
            queryset = queryset.filter(**filters)
        return queryset.order_by("created_at", "id")

    def perform_create(self, serializer):
        require(self.request.user, "offering.manage", serializer.validated_data["offering"].pk)
        serializer.save()

    def partial_update(self, request, *args, **kwargs):
        enrollment = self.get_object()
        serializer = EnrollmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require(request.user, "grades.edit", enrollment.offering_id)
        updated = services.update_enrollment_status(
            enrollment=enrollment, actor=request.user, **serializer.validated_data
        )
        return Response(self.get_serializer(updated).data)


class InstructorWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instructor_assignments = RoleAssignment.objects.filter(
            user=request.user, role_id="instructor", revoked_at__isnull=True
        )
        if not instructor_assignments.exists():
            raise PermissionDenied("Instructor access is required.")
        exact_grants = DirectCapabilityGrant.objects.filter(
            user=request.user, capability_id="grades.view", revoked_at__isnull=True
        ).values_list("scope_id", flat=True)
        offering_scopes = Scope.objects.filter(
            Q(pk__in=instructor_assignments.values_list("scope_id", flat=True))
            | Q(pk__in=exact_grants),
            kind=Scope.Kind.OFFERING,
        )
        offerings = (
            CourseOffering.objects.filter(pk__in=offering_scopes)
            .select_related("course", "term", "program")
            .order_by("term__year", "term__season", "course__code", "section")
        )
        response = []
        for offering in offerings:
            enrollments = scoping.scope_enrollments(
                request.user,
                Enrollment.objects.filter(offering=offering).select_related("student"),
            ).order_by("student__last_name", "student__first_name", "student__username")
            response.append(
                {
                    "id": str(offering.pk),
                    "label": f"{offering.course.code} · {offering.section}",
                    "course": offering.course.title,
                    "program": offering.program.title,
                    "term": f"{offering.term.year} {offering.term.season.title()}",
                    "roster": [
                        {
                            "enrollment_id": str(row.pk),
                            "name": (
                                f"{row.student.first_name} {row.student.last_name}".strip()
                                or row.student.username
                            ),
                            "status": row.status,
                        }
                        for row in enrollments
                    ],
                }
            )
        result = Response({"offerings": response})
        result["Cache-Control"] = "no-store"
        return result


class StudentWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        assigned_offerings = RoleAssignment.objects.filter(
            user=request.user, role_id="student", revoked_at__isnull=True
        ).values_list("scope_id", flat=True)
        if not assigned_offerings.exists():
            raise PermissionDenied("Student access is required.")
        enrollments = (
            Enrollment.objects.filter(student=request.user, offering_id__in=assigned_offerings)
            .select_related("offering__course", "offering__term", "offering__program")
            .order_by("offering__term__year", "offering__term__season", "offering__course__code")
        )
        result = Response(
            {
                "courses": [
                    {
                        "enrollment_id": str(row.pk),
                        "offering_id": str(row.offering_id),
                        "course_code": row.offering.course.code,
                        "course": row.offering.course.title,
                        "program": row.offering.program.title,
                        "term": f"{row.offering.term.year} {row.offering.term.season.title()}",
                        "section": row.offering.section,
                        "enrollment_status": row.status,
                    }
                    for row in enrollments
                ],
                "outcomes": [],
            }
        )
        result["Cache-Control"] = "no-store"
        return result


class CoordinatorWorkspaceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        program_scopes = Scope.objects.filter(
            authorization.scope_filter(request.user, "program.manage", prefix=""),
            kind=Scope.Kind.PROGRAM,
        )
        if not program_scopes.exists():
            raise PermissionDenied("Program coordinator access is required.")
        programs = Program.objects.filter(pk__in=program_scopes).select_related("department")
        offerings = CourseOffering.objects.filter(program__in=programs).select_related(
            "course", "term"
        )
        memberships = ProgramMembership.objects.filter(program__in=programs).select_related(
            "user", "program"
        )
        result = Response(
            {
                "programs": [
                    {
                        "id": str(program.pk),
                        "label": program.title,
                        "department": program.department.name,
                    }
                    for program in programs
                ],
                "offerings": [
                    {
                        "id": str(offering.pk),
                        "program_id": str(offering.program_id),
                        "label": f"{offering.course.code} · {offering.section}",
                        "course": offering.course.title,
                        "term": f"{offering.term.year} {offering.term.season.title()}",
                        "enrolled": offering.enrollments.count(),
                    }
                    for offering in offerings
                ],
                "students": [
                    {
                        **user_data(membership.user),
                        "program_id": str(membership.program_id),
                        "student_number": membership.student_number,
                        "membership_status": membership.status,
                    }
                    for membership in memberships
                ],
            }
        )
        result["Cache-Control"] = "no-store"
        return result
