from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services import WorkspaceService, academic_service_provider


class AcademicWorkspaceController(APIView):
    permission_classes = [IsAuthenticated]
    service_provider = academic_service_provider
    service_class = WorkspaceService

    def get_service(self):
        return self.service_provider.provide(self.service_class, actor=self.request.user)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class InstructorWorkspaceController(AcademicWorkspaceController):
    def get(self, request):
        service = self.get_service()
        offerings = service.instructor_offerings()
        return Response(
            {
                "offerings": [
                    {
                        "id": str(offering.pk),
                        "label": f"{offering.course.code} · {offering.section}",
                        "course": offering.course.title,
                        "program": offering.program.title,
                        "term": f"{offering.term.year} {offering.term.season.title()}",
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
                            for enrollment in service.instructor_roster(offering)
                        ],
                    }
                    for offering in offerings
                ]
            }
        )


class StudentWorkspaceController(AcademicWorkspaceController):
    def get(self, request):
        enrollments = self.get_service().student_enrollments()
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


class CoordinatorWorkspaceController(AcademicWorkspaceController):
    def get(self, request):
        service = self.get_service()
        programs = service.coordinator_programs()
        offerings = service.coordinator_offerings(programs)
        memberships = service.coordinator_memberships(programs)
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
                "students": [service.membership_user_data(row) for row in memberships],
            }
        )
