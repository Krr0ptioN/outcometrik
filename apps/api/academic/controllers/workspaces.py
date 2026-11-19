from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..decorators import controller, get
from ..services import WorkspaceService, academic_service_provider


@controller("workspaces/instructor")
class InstructorWorkspaceController(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, service: WorkspaceService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(WorkspaceService)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @get()
    def get(self, request):
        actor = getattr(request, "user", None)
        offerings = self.service.instructor_offerings(actor=actor)
        return Response(
            {
                "offerings": [
                    {
                        "id": str(offering.pk),
                        "label": f"{offering.course.code} · {offering.section}",
                        "course": offering.course.title,
                        "program": offering.program.title,
                        "term": f"{offering.term.year} {offering.term.season.title()}",
                        "input_revision": offering.input_revision,
                        "roster": [
                            {
                                "enrollment_id": str(enrollment.pk),
                                "name": (
                                    f"{enrollment.student.first_name} "
                                    f"{enrollment.student.last_name}"
                                ).strip()
                                or enrollment.student.username,
                                "status": enrollment.status,
                            }
                            for enrollment in self.service.instructor_roster(offering, actor=actor)
                        ],
                    }
                    for offering in offerings
                ]
            }
        )


@controller("workspaces/student")
class StudentWorkspaceController(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, service: WorkspaceService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(WorkspaceService)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @get()
    def get(self, request):
        actor = getattr(request, "user", None)
        enrollments = self.service.student_enrollments(actor=actor)
        return Response(
            {
                "courses": [
                    {
                        "enrollment_id": str(enrollment.pk),
                        "offering_id": str(enrollment.offering_id),
                        "course_code": enrollment.offering.course.code,
                        "course": enrollment.offering.course.title,
                        "program": enrollment.offering.program.title,
                        "term": (
                            f"{enrollment.offering.term.year} "
                            f"{enrollment.offering.term.season.title()}"
                        ),
                        "section": enrollment.offering.section,
                        "enrollment_status": enrollment.status,
                    }
                    for enrollment in enrollments
                ],
                "outcomes": [],
            }
        )


@controller("workspaces/coordinator")
class CoordinatorWorkspaceController(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, service: WorkspaceService | None = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or academic_service_provider.provide(WorkspaceService)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @get()
    def get(self, request):
        actor = getattr(request, "user", None)
        programs = self.service.coordinator_programs(actor=actor)
        offerings = self.service.coordinator_offerings(programs, actor=actor)
        memberships = self.service.coordinator_memberships(programs, actor=actor)
        return Response(
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
                "students": [self.service.membership_user_data(row) for row in memberships],
            }
        )
