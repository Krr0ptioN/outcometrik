from ..decorators import controller
from ..serializers import ProgramCourseSerializer
from ..services import ProgramCourseService
from .base import AcademicController


@controller("program-courses", basename="program-course")
class ProgramCourseController(AcademicController):
    serializer_class = ProgramCourseSerializer
    service_class = ProgramCourseService
    filter_fields = ("program", "course", "status")
