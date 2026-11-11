from ..serializers import DepartmentSerializer
from ..services import DepartmentService
from .base import AcademicController


class DepartmentController(AcademicController):
    serializer_class = DepartmentSerializer
    service_class = DepartmentService
    filter_fields = ("institution", "code")
