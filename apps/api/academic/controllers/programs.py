from ..decorators import controller
from ..serializers import ProgramSerializer
from ..services import ProgramService
from .base import AcademicController


@controller("programs", basename="program")
class ProgramController(AcademicController):
    serializer_class = ProgramSerializer
    service_class = ProgramService
    filter_fields = ("department", "status", "code")
