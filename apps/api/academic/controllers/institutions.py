from ..serializers import InstitutionSerializer
from ..services import InstitutionService
from .base import AcademicController


class InstitutionController(AcademicController):
    serializer_class = InstitutionSerializer
    service_class = InstitutionService
    filter_fields = ("code",)
