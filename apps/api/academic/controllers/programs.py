from ..serializers import ProgramSerializer
from ..services import ProgramService
from .base import AcademicController


class ProgramController(AcademicController):
    serializer_class = ProgramSerializer
    service_class = ProgramService
    filter_fields = ("department", "status", "code")
