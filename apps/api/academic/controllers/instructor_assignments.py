from ..decorators import controller
from ..serializers import InstructorAssignmentSerializer
from ..services import InstructorAssignmentService
from .base import AcademicController


@controller("instructor-assignments", basename="instructor-assignment")
class InstructorAssignmentController(AcademicController):
    serializer_class = InstructorAssignmentSerializer
    service_class = InstructorAssignmentService
    filter_fields = ("offering", "user", "assignment_role")
