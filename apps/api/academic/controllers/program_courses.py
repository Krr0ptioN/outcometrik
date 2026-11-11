from ..serializers import ProgramCourseSerializer
from ..services import ProgramCourseService
from .base import AcademicController


class ProgramCourseController(AcademicController):
    serializer_class = ProgramCourseSerializer
    service_class = ProgramCourseService
    filter_fields = ("program", "course", "status")
