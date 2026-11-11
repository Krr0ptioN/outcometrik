from ..serializers import AcademicTermSerializer
from ..services import AcademicTermService
from .base import AcademicController


class AcademicTermController(AcademicController):
    serializer_class = AcademicTermSerializer
    service_class = AcademicTermService
    filter_fields = ("institution", "year", "season")
